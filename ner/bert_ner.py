import tensorflow as tf
import os
from dmgr.builder import read_json
import pandas as pd
import numpy as np
# from fastprogress import master_bar, progress_bar
import math
# https://github.com/bhuvanakundumani/BERT-NER-TF2/blob/4a6bdbb873e344e515f72d88e8acdb6c3a2b3acb/run_ner.py
from .BERT_NER_TF2.model import BertNer
from .BERT_NER_TF2.optimization import AdamWeightDecay, WarmUp
from shutil import copyfile, copytree
import json


def initialize(model_path, train_dataset='NER', config={},
               train_batch_size=32, num_train_epochs=3, warmup_proportion=0.1,
               learning_rate=5e-5, weight_decay=0.01, adam_epsilon=1e-8, I_AM_POOR=True):
    if not os.path.isfile(os.path.join(model_path, "model.h5")):
        input_dataset_config = read_json(os.path.join("data/datasets/", train_dataset + '.json'))
        vocab_file = os.path.join(
            f'data/datasets/TEXT_BERT/bert.vocab')  # TODO : dmgr NER need to dump 'data/datasets/NER/bert.vocab'
        dataset_file = os.path.join(input_dataset_config['dataset_path'], 'processed.pkl.gz')
        train_batch_size = 4 if I_AM_POOR else train_batch_size

        bert_model = config["embedder"]["bert"]["model"]
        bert_model_pooled = config["embedder"]["bert"]["pooled_model"]
        input_size = config["embedder"]["bert"]["max_seq_len"]

        orig_bert_model_path = os.path.abspath(config["embedder"]["bert"]["model_dir"])
        orig_bert_config_path = os.path.join(orig_bert_model_path, "bert_config.json")
        bert_config_path = os.path.join(model_path, "bert_config.json")
        bert_pretrain_ckpt_path = os.path.join(model_path, "pretrain_ckpt")

        if not os.path.isfile(bert_config_path):
            copyfile(orig_bert_config_path, bert_config_path)
            # os.symlink(orig_bert_model_path, bert_ckpt_path) # TODO : Use this if overwrite is OK
            copytree(orig_bert_model_path, bert_pretrain_ckpt_path)

        label_index = {'O': 1, 'MISC': 2, 'NUM': 3, 'TIM': 4, 'ORG': 5, 'PER': 6, 'LOC': 7,
                       '[CLS]': 8, '[SEP]': 9}
        len_label_index = len(label_index) + 1
        shuffled_train_data, len_train_features = _prepare_data(dataset_file, vocab_file, input_size, label_index)
        batched_train_data = shuffled_train_data.batch(train_batch_size)

        ner, train_step, loss_metric, pb_max_len = _setup_train(
            bert_pretrain_ckpt_path, learning_rate, train_batch_size, num_train_epochs,
            warmup_proportion, weight_decay, adam_epsilon, max_seq_length=input_size,
            num_labels=len_label_index, len_train_features=len_train_features)

        loss_history = _train(batched_train_data, train_step, loss_metric, ner, model_path,
               config, bert_pretrain_ckpt_path, label_index, pb_max_len)
        loss_history_summary = \
            {i * 100: sum(loss_history[100*i:100*i + 100]) / 100.0 for i in range(int(len(loss_history) / 100))}

        if "ner" not in config:
            config["ner"] = {}
        config["ner"]["train_loss_history"] = loss_history_summary

    return config


def _pad(x, size, pad):
    return x[:size] + [pad] * max(0, size - len(x))


def _train(batched_train_data, train_step, loss_metric, ner, model_path, config, bert_pretrain_ckpt_path, label_index,
           pb_max_len):
    input_size = config["embedder"]["bert"]["max_seq_len"]
    loss_history = []

    for train_data in batched_train_data.as_numpy_iterator():
        input_ids, input_mask, segment_ids, valid_ids, label_ids, label_mask = train_data
        loss = train_step(input_ids, input_mask, segment_ids, valid_ids, label_ids, label_mask)
        loss_metric(loss)
        if len(loss_history) % 100 == 0:
            print(f'{len(loss_history)}/{pb_max_len}, loss : {loss_metric.result()}')
            print({i * 100: sum(loss_history[i*100:100*i + 100]) / 100.0 for i in range(int(len(loss_history) / 100))})
        if len(loss_history) % 5000 == 0:
            ner.save_weights(os.path.join(model_path, "model_checkpoint.h5")) # checkpoint
        loss_history.append(float(loss_metric.result()))
        loss_metric.reset_states()

    # model weight save
    ner.save_weights(os.path.join(model_path, "model.h5"))
    # copy vocab to model dir
    copyfile(os.path.join(config["embedder"]["bert"]["vocab_file"]), os.path.join(model_path, "vocab.txt"))
    # save label_map and max_seq_length of trained model
    model_config = {"bert_pretrain_ckpt_path": bert_pretrain_ckpt_path, "do_lower": False,
                    "max_seq_length": input_size, "num_labels": len(label_index),
                    "label_map": label_index}
    json.dump(model_config, open(os.path.join(model_path, "model_config.json"), "w"), indent=4)

    return loss_history


def _setup_train(ckpt_path, learning_rate, train_batch_size, num_train_epochs, warmup_proportion,
                 weight_decay, adam_epsilon, max_seq_length, num_labels, len_train_features):
    num_train_optimization_steps = int(
        len_train_features / train_batch_size) * num_train_epochs
    warmup_steps = int(warmup_proportion *
                       num_train_optimization_steps)
    learning_rate_fn = tf.keras.optimizers.schedules.PolynomialDecay(initial_learning_rate=learning_rate,
                                                                     decay_steps=num_train_optimization_steps,
                                                                     end_learning_rate=0.0)
    if warmup_steps:
        learning_rate_fn = WarmUp(initial_learning_rate=learning_rate,
                                  decay_schedule_fn=learning_rate_fn,
                                  warmup_steps=warmup_steps)
    optimizer = AdamWeightDecay(
        learning_rate=learning_rate_fn,
        weight_decay_rate=weight_decay,
        beta_1=0.9,
        beta_2=0.999,
        epsilon=adam_epsilon,
        exclude_from_weight_decay=['layer_norm', 'bias'])

    ner = BertNer(ckpt_path, tf.float32, num_labels, max_seq_length)
    # loss_fct = tf.keras.losses.SparseCategoricalCrossentropy(reduction=tf.keras.losses.Reduction.NONE)
    loss_fct = tf.keras.losses.SparseCategoricalCrossentropy(reduction=tf.keras.losses.Reduction.NONE)
    loss11_fct = tf.keras.losses.SparseCategoricalCrossentropy(from_logits=True,
                                                               reduction=tf.keras.losses.Reduction.NONE)
    l_fct = tf.keras.losses.SparseCategoricalCrossentropy(from_logits=True)

    loss_metric = tf.keras.metrics.Mean()
    pb_max_len = math.ceil(float(len_train_features) / float(train_batch_size))

    def train_step(input_ids, input_mask, segment_ids, valid_ids, label_ids, label_mask):
        with tf.GradientTape() as tape:
            # TODO : check model spec : pooling, logit, normalization ...
            logits = ner(input_ids, input_mask, segment_ids, valid_ids,
                         training=True)  # batchsize, max_seq_length, num_labels
            label_ids_masked = tf.boolean_mask(label_ids, label_mask)
            logits_masked = tf.boolean_mask(logits, label_mask)
            loss = loss_fct(label_ids_masked, logits_masked)

        grads = tape.gradient(loss, ner.trainable_variables)
        optimizer.apply_gradients(list(zip(grads, ner.trainable_variables)))
        return loss

    return ner, train_step, loss_metric, pb_max_len


def _prepare_data(dataset_file, vocab_file, input_size, label_index):
    df = pd.read_pickle(dataset_file, compression="infer")
    with open(vocab_file, 'r') as fp:
        vocab = [x.strip() for x in fp.readlines()]
    # print(vocab)
    special_index = {
        '[UNK]': vocab.index('[UNK]'),
        '[PAD]': vocab.index('[PAD]'),
        '< S >': vocab.index('< S >'),
        '< T >': vocab.index('< T >'),
        '[CLS]': vocab.index('[CLS]'),
        '[SEP]': vocab.index('[SEP]'),
    }

    train_features = []
    for index, row in df.iterrows():
        tokens_text = ['[CLS]'] + row["tokens"] + ['[SEP]']
        tokens = [special_index['[CLS]']] + row["index"] + [special_index['[SEP]']]
        tags = [label_index[x] for x in (['[CLS]'] + row["tags"] + ['[SEP]'])]

        train_feature = {
            'input_ids': _pad(tokens, input_size, special_index["[PAD]"]),
            'input_mask': _pad([1] * len(tokens), input_size, special_index["[PAD]"]),
            'segment_ids': [0] * input_size,
            'label_ids': _pad(tags, input_size, 0),
            'label_mask': _pad([True] * len(tags), input_size, False),
            'valid_ids': _pad([(1 if (token.startswith('_') or token.startswith('[')) else 0) for token in tokens_text],
                              input_size, 0),
        }
        train_features.append(train_feature)

    all_input_ids = tf.data.Dataset.from_tensor_slices(np.asarray([f["input_ids"] for f in train_features]))
    all_input_mask = tf.data.Dataset.from_tensor_slices(np.asarray([f["input_mask"] for f in train_features]))
    all_segment_ids = tf.data.Dataset.from_tensor_slices(np.asarray([f["segment_ids"] for f in train_features]))
    all_valid_ids = tf.data.Dataset.from_tensor_slices(np.asarray([f["valid_ids"] for f in train_features]))
    all_label_mask = tf.data.Dataset.from_tensor_slices(np.asarray([f["label_mask"] for f in train_features]))
    all_label_ids = tf.data.Dataset.from_tensor_slices(np.asarray([f["label_ids"] for f in train_features]))

    # Dataset using tf.data
    train_data = tf.data.Dataset.zip(
        (all_input_ids, all_input_mask, all_segment_ids, all_valid_ids, all_label_ids, all_label_mask))
    shuffled_train_data = train_data.shuffle(buffer_size=int(len(train_features) * 0.1),
                                             seed=12345,
                                             reshuffle_each_iteration=True)
    return shuffled_train_data, len(train_features)
