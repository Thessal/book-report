from tokenizer import *
from constant import *
from document_model.file_io import TextIO
import io

# for fp in files:
#     lines = [x.strip() for x in fp.readlines()]
#     lines = TextIO.heuristic_formatting(lines, debug=False)

# a = io.BytesIO()
# a.write("hello".encode())
# txt = a.getvalue()
# txt = txt.decode("utf-8")
# print(txt)


# Monkey patch for create_pretraining_data
import tensorflow as tf

tf.flags = tf.compat.v1.flags
tf.python_io = tf.compat.v1.python_io
tf.logging = tf.compat.v1.logging
tf.gfile = tf.compat.v1.gfile
import os
import sys
import multiprocessing

sys.path.append(os.path.dirname(os.path.abspath(os.path.dirname(__file__))) + "/encoder/bert")
from .bert import create_pretraining_data as pre

textio = TextIO(None)


class BertModel:
    def __init__(self):
        self.shape = (1, 128)
        self.tokenizer = TokenizerSpm(
            TOKENIZER_DIR
        )
        self.tokenizer.load(enable_tf=False)
        return

    def bert_preprocess_model(self, text):
        # [PAD] 200000
        # [UNK] 0
        # [CLS] 200001
        # [SEP] 200002
        # [MASK] 200003
        # < S > 1
        # < T > 2
        N = self.shape[1]
        output = [y for x in self.tokenizer.tokenize(text) for y in x]
        output = output[:min(len(output), N)]
        return {
            'input_mask': (output + [200000] * (N - len(output))),
            'input_word_ids': [1] * len(output) + [0] * (N - len(output)),
            'input_type_ids': [0] * len(output),
        }

    def create_pretraining_data(self, files_in, files_out, vocab_file, pool_size=7):
        pre.FLAGS.do_lower_case = False
        pre.FLAGS.do_whole_word_mask = False
        pre.FLAGS.max_seq_length = 128
        pre.FLAGS.max_predictions_per_seq = 20
        pre.FLAGS.random_seed = 12345
        pre.FLAGS.dupe_factor = 10
        pre.FLAGS.masked_lm_prob = 0.15
        pre.FLAGS.short_seq_prob = 0  # ", 0.1,
        pre.FLAGS.vocab_file = f"/dev/shm/temp.vocab"

        # Convert sentencepiece vocab into BERT vocab
        if not os.path.isfile(pre.FLAGS.vocab_file):
            with open(vocab_file, "r") as fp:
                vocab = [x.strip().split('\t') for x in fp.readlines()]
                if vocab[0][0] == '< unk >':
                    vocab[0][0] = '[UNK]'
                if vocab[1][0] == '< s >':
                    vocab[1][0] = '< S >'
                if vocab[2][0] == '< / s >':
                    vocab[2][0] = '< T >'

                vocab_terms = [x[0] for x in vocab]
                for x in ["[PAD]", "[UNK]", "[CLS]", "[SEP]", "[MASK]", "< S >", "< T >"]:
                    if x not in vocab_terms:
                        vocab.append([x, '0'])

                vocab_terms = [x[0] for x in vocab]
                with open(pre.FLAGS.vocab_file, "w", encoding="utf-8") as tmpf:
                    tmpf.write('\n'.join(vocab_terms))

        # Replace tokenizer into my version
        if pre.tokenization.FullTokenizer.tokenize != self.tokenizer.tokenize:
            pre.tokenization.FullTokenizer.tokenize = self.tokenizer.tokenize

        with multiprocessing.Pool(processes=pool_size) as pool:
            results = pool.starmap(self._create_pretraining_data, zip(files_in, files_out))
        print("Errors:")
        print('\n'.join([r for r in results if r]))

    def _create_pretraining_data(self, file_in, file_out):
        """
        Convert raw text into BERT train examples
        :param files_in: text file
        :param files_out: BERT train file
        :param vocab_file: sentencepiece vocab file
        :return:
        """
        worker_id = multiprocessing.current_process().name
        file_in_formatted = f"/dev/shm/temp{worker_id}.txt"

        # Convert raw text into BERT format text
        with open(file_in, "r") as fp:
            lines = [x.strip() for x in fp.readlines()]
            output = '\n'.join(textio.heuristic_formatting(lines))
            with open(file_in_formatted, "w", encoding="utf-8") as tmpf:
                tmpf.write(output)

        # Create pretraining data
        try:
            os.makedirs(os.path.dirname(file_out), exist_ok=True)
            pre.FLAGS.input_file = file_in_formatted
            pre.FLAGS.output_file = file_out
            pre.main(None)
            assert(pre.FLAGS.input_file == file_in_formatted) # ¯\_(ツ)_/¯
            assert(pre.FLAGS.output_file == file_out)
        except Exception as e:
            print()
            print("===Error===")
            print(file_in)
            print(e)
            print("===========")
            return file_in+'\t'+str(e)
        return None


