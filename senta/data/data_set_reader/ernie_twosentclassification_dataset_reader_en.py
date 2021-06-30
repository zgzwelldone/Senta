"""task reader"""
import csv
import json
import logging
import os
import random
import traceback
from collections import namedtuple

import numpy as np
from paddle import fluid

from senta.common.register import RegisterSet
from senta.common.rule import InstanceName
from senta.data.data_set_reader.base_dataset_reader import BaseDataSetReader
from senta.data.data_set_reader.basic_dataset_reader_without_fields import TaskBaseReader
from senta.data.util_helper import pad_batch_data


@RegisterSet.data_set_reader.register
class TwoSentClassifyReaderEn(TaskBaseReader):
    """classify reader"""

    def __init__(self, name, fields, config):

        BaseDataSetReader.__init__(self, name, fields, config)
        self.max_seq_len = config.extra_params.get("max_seq_len", 512)
        self.do_lower_case = config.extra_params.get("do_lower_case", False)
        self.vocab_path = config.extra_params.get("vocab_path")
        self.text_field_more_than_3 = config.extra_params.get("text_field_more_than_3", False)
        self.data_augmentation = config.extra_params.get("data_augmentation", False)
        self.in_tokens = config.extra_params.get("in_tokens", False)
        self.spm_model_path = config.extra_params.get("spm_model_path")
        self.tokenizer_name = config.extra_params.get("tokenizer", "FullTokenizerSpm")
        self.is_classify = config.extra_params.get("is_classify", True)
        self.is_regression = config.extra_params.get("is_regression", False)
        self.use_multi_gpu_test = config.extra_params.get("use_multi_gpu_test", True)
        self.label_map_config = config.extra_params.get("label_map_config")

        params = {"do_lower_case": self.do_lower_case}
        tokenizer_class = RegisterSet.tokenizer.__getitem__(self.tokenizer_name)
        self.tokenizer = tokenizer_class(vocab_file=self.vocab_path, params=params)

        self.vocab = self.tokenizer.vocabulary.vocab_dict
        self.pad_id = self.vocab["[PAD]"]
        self.cls_id = self.vocab["[CLS]"]
        self.sep_id = self.vocab["[SEP]"]

        if "train" in self.name:
            self.phase = InstanceName.TRAINING
        elif "dev" in self.name:
            self.phase = InstanceName.EVALUATE
        elif "test" in self.name:
            self.phase = InstanceName.TEST
        else:
            self.phase = None

        self.trainer_id = 0
        self.trainer_nums = 1
        if os.getenv("PADDLE_TRAINER_ID"):
            self.trainer_id = int(os.getenv("PADDLE_TRAINER_ID"))
        if os.getenv("PADDLE_NODES_NUM"):
            self.trainer_nums = int(os.getenv("PADDLE_TRAINERS_NUM"))

        if "train" in self.name:
            self.dev_count = self.trainer_nums
        elif "dev" in self.name or "test" in self.name or "predict" in self.name:
            self.dev_count = 1
            if self.use_multi_gpu_test:
                self.dev_count = min(self.trainer_nums, 8)
        else:
            logging.error("the phase must be train, eval or test !")

        self.current_example = 0
        self.current_epoch = 0
        self.num_examples = 0

        if self.label_map_config:
            with open(self.label_map_config) as f:
                self.label_map = json.load(f)
        else:
            self.label_map = None

    def create_reader(self):
        """create reader"""
        shapes = [[-1, self.max_seq_len, 1], [-1, self.max_seq_len, 1], [-1, self.max_seq_len, 1],
                  [-1, self.max_seq_len, 1], [-1, self.max_seq_len, 1], [-1, 1], [-1, 1]]
        if self.is_classify:
            dtypes = ['int64', 'int64', 'int64', 'int64', 'float32', 'int64', 'int64']
        elif self.is_regression:
            dtypes = ['int64', 'int64', 'int64', 'int64', 'float32', 'float32', 'int64']
        lod_levels = [0, 0, 0, 0, 0, 0, 0]

        self.paddle_py_reader = fluid.layers.py_reader(
            capacity=50,
            shapes=shapes,
            dtypes=dtypes,
            lod_levels=lod_levels,
            name=self.name,
            use_double_buffer=True)

        logging.debug("{0} create py_reader shape = {1}, types = {2}, \
                      level = {3}: ".format(self.name, shapes, dtypes, lod_levels))

    def convert_fields_to_dict(self, field_list, need_emb=False):
        """convert fileds to dict"""
        fields_instance = {}

        record_id_dict_text_a = {
            InstanceName.SRC_IDS: field_list[0],
            InstanceName.SENTENCE_IDS: field_list[1],
            InstanceName.POS_IDS: field_list[2],
            InstanceName.TASK_IDS: field_list[3],
            InstanceName.MASK_IDS: field_list[4]
        }
        record_dict_text_a = {
            InstanceName.RECORD_ID: record_id_dict_text_a,
            InstanceName.RECORD_EMB: None
        }
        fields_instance["text_a"] = record_dict_text_a

        record_id_dict_label = {
            InstanceName.SRC_IDS: field_list[5]
        }
        record_dict_label = {
            InstanceName.RECORD_ID: record_id_dict_label,
            InstanceName.RECORD_EMB: None
        }
        fields_instance["label"] = record_dict_label

        record_id_dict_qid = {
            InstanceName.SRC_IDS: field_list[6]
        }
        record_dict_qid = {
            InstanceName.RECORD_ID: record_id_dict_qid,
            InstanceName.RECORD_EMB: None
        }
        fields_instance["qid"] = record_dict_qid

        return fields_instance

    def read_files(self, input_file, quotechar=None):
        """Reads a tab separated value file."""
        with open(input_file, "r") as f:
            try:
                reader = csv.reader(f, delimiter="\t", quotechar=quotechar)
                headers = next(reader)
                text_indices = [
                    index for index, h in enumerate(headers) if h != "label"
                ]
                label_indices = [
                    index for index, h in enumerate(headers) if h == "label"
                ]

                Example = namedtuple('Example', headers)

                examples = []
                i = 0
                for line in reader:
                    for index, text in enumerate(line):
                        if index in text_indices:
                            line[index] = text  # .replace(' ', '')
                        elif index in label_indices:

                            text_ind = text_indices[0]
                            label_ind = index
                            text = line[text_ind]
                            label = line[label_ind]

                            if self.data_augmentation and 'train' in input_file and random.random() < 0.2:

                                toks = text.split(' ')
                                for _ in range(2):
                                    drop_ind = random.randint(0, len(toks) - 1)
                                    toks.pop(drop_ind)

                                line[text_ind] = ' '.join(toks)

                    example = Example(*line)
                    examples.append(example)
                return examples
            except Exception:
                logging.error("error in read tsv")
                logging.error("traceback.format_exc():\n%s" % traceback.format_exc())

    def serialize_batch_records(self, batch_records):
        """pad batch records"""
        batch_token_ids = [record.token_ids for record in batch_records]
        batch_text_type_ids = [record.text_type_ids for record in batch_records]
        batch_position_ids = [record.position_ids for record in batch_records]
        batch_task_ids = [record.task_ids for record in batch_records]
        if "predict" not in self.name:
            batch_labels = [record.label_id for record in batch_records]
            if self.is_classify:
                batch_labels = np.array(batch_labels).astype("int64").reshape([-1, 1])
            elif self.is_regression:
                batch_labels = np.array(batch_labels).astype("float32").reshape([-1, 1])
        else:
            if self.is_classify:
                batch_labels = np.array([]).astype("int64").reshape([-1, 1])
            elif self.is_regression:
                batch_labels = np.array([]).astype("float32").reshape([-1, 1])

        if batch_records[0].qid:
            batch_qids = [record.qid for record in batch_records]
            batch_qids = np.array(batch_qids).astype("int64").reshape([-1, 1])
        else:
            batch_qids = np.array([]).astype("int64").reshape([-1, 1])

        # padding
        padded_token_ids, input_mask = pad_batch_data(
            batch_token_ids, pad_idx=self.pad_id, return_input_mask=True)
        padded_text_type_ids = pad_batch_data(
            batch_text_type_ids, pad_idx=self.pad_id)
        padded_position_ids = pad_batch_data(
            batch_position_ids, pad_idx=self.pad_id)
        padded_task_ids = pad_batch_data(
            batch_task_ids, pad_idx=0)

        return_list = [
            padded_token_ids, padded_text_type_ids, padded_position_ids,
            padded_task_ids, input_mask, batch_labels, batch_qids
        ]

        return return_list
