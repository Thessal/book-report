import tensorflow as tf
import os
from dmgr.builder import read_json
import pandas as pd
import numpy as np
# from fastprogress import master_bar, progress_bar
import math
# https://github.com/bhuvanakundumani/BERT-NER-TF2/blob/4a6bdbb873e344e515f72d88e8acdb6c3a2b3acb/run_ner.py
from ner.BERT_NER_TF2.model import BertNer
from ner.BERT_NER_TF2.optimization import AdamWeightDecay, WarmUp
from shutil import copyfile, copytree

from ner.bert_ner import _setup_train, _prepare_data, _pad


input_dataset_config = read_json("data/datasets/NER.json")
vocab_file = os.path.join(f'data/datasets/TEXT_BERT/bert.vocab')
dataset_file = os.path.join(input_dataset_config['dataset_path'], 'processed.pkl.gz')

orig_bert_model_path = 'data/models/bert'
orig_bert_config_path = 'data/models/bert/bert_config.json'
model_path = 'data/models/bert_ner'
bert_config_path = 'data/models/bert_ner/bert_config.json'
bert_ckpt_path = 'data/models/bert_ner/pretrain_ckpt'
label_index = {'O': 1, 'MISC': 2, 'NUM': 3, 'TIM': 4, 'ORG': 5, 'PER': 6, 'LOC': 7, '[CLS]': 8, '[SEP]': 9}


## Test _setup_train
len_label_index = len(label_index)+1
len_train_features = 30
train_batch_size = 2
ner, train_step, loss_metric, pb_max_len = _setup_train(model_path, train_batch_size=train_batch_size, num_train_epochs=3, warmup_proportion=0.1,
                   learning_rate=5e-5, weight_decay=0.01, adam_epsilon=1e-8, max_seq_length=128,
                   num_labels = len_label_index, len_train_features=len_train_features)


## Generate data
shuffled_train_data, len_train_features = _prepare_data(dataset_file, vocab_file, input_size=128, label_index=label_index)
batched_train_data = shuffled_train_data.batch(batch_size=train_batch_size)


## Train
input_ids, input_mask, segment_ids, valid_ids, label_ids, label_mask = next(batched_train_data.as_numpy_iterator())
loss = train_step(input_ids, input_mask, segment_ids, valid_ids, label_ids, label_mask)
loss_metric(loss)
print(f'loss : {loss_metric.result()}')

## Train
for train_data in batched_train_data.as_numpy_iterator():
    input_ids, input_mask, segment_ids, valid_ids, label_ids, label_mask = train_data
    loss = train_step(input_ids, input_mask, segment_ids, valid_ids, label_ids, label_mask)
    loss_metric(loss)
    print(f'loss : {loss_metric.result()}')
    loss_metric.reset_states()