# -*- coding: utf-8 -*
"""
:py:class:`ErnieTextFieldReader`

"""
import logging

import paddle

from senta.common.register import RegisterSet
from senta.common.rule import DataShape, FieldLength, InstanceName
from senta.data.field_reader.base_field_reader import BaseFieldReader
from senta.data.util_helper import pad_batch_data
from senta.modules.token_embedding.ernie_embedding import ErnieTokenEmbedding
from senta.utils.util_helper import truncation_words


@RegisterSet.field_reader.register
class ErnieTextFieldReader(BaseFieldReader):
    """使用ernie的文本类型的field_reader，用户不需要自己分词
        处理规则是：自动添加padding,mask,position,task,sentence,并返回length
        """

    def __init__(self, field_config):
        """
        :param field_config:
        """
        # 换成2.7的语法试试
        BaseFieldReader.__init__(self, field_config=field_config)

        if self.field_config.tokenizer_info:
            tokenizer_class = RegisterSet.tokenizer.__getitem__(self.field_config.tokenizer_info["type"])
            params = None
            if self.field_config.tokenizer_info.__contains__("params"):
                params = self.field_config.tokenizer_info["params"]
            self.tokenizer = tokenizer_class(vocab_file=self.field_config.vocab_path,
                                             split_char=self.field_config.tokenizer_info["split_char"],
                                             unk_token=self.field_config.tokenizer_info["unk_token"],
                                             params=params)

        logging.info("embedding_info = %s" % self.field_config.embedding_info)
        if self.field_config.embedding_info and self.field_config.embedding_info["use_reader_emb"]:
            self.token_embedding = ErnieTokenEmbedding(emb_dim=self.field_config.embedding_info["emb_dim"],
                                                       vocab_size=self.tokenizer.vocabulary.get_vocab_size(),
                                                       params_path=self.field_config.embedding_info["config_path"])

    def init_reader(self):
        """ 初始化reader格式
                :return: reader的shape[]、type[]、level[]
                """
        shape = []
        types = []
        levels = []
        if self.field_config.data_type == DataShape.STRING:
            """src_ids"""
            shape.append([-1, self.field_config.max_seq_len, 1])
            levels.append(0)
            types.append('int64')
        else:
            raise TypeError("ErnieTextFieldReader's data_type must string")

        """sentence_ids"""
        shape.append([-1, self.field_config.max_seq_len, 1])
        levels.append(0)
        types.append('int64')
        """position_ids"""
        shape.append([-1, self.field_config.max_seq_len, 1])
        levels.append(0)
        types.append('int64')
        """mask_ids"""
        shape.append([-1, self.field_config.max_seq_len, 1])
        levels.append(0)
        types.append('float32')
        """task_ids"""
        shape.append([-1, self.field_config.max_seq_len, 1])
        levels.append(0)
        types.append('int64')
        """seq_lens"""
        if paddle.__version__[:3] <= '1.5':
            shape.append([-1, 1])
        else:
            shape.append([-1])
        levels.append(0)
        types.append('int64')
        return shape, types, levels

    def convert_texts_to_ids(self, batch_text):
        """将一个batch的明文text转成id
        :param batch_text:
        :return:
        """
        src_ids = []
        position_ids = []
        task_ids = []
        sentence_ids = []
        for text in batch_text:
            if self.field_config.need_convert:
                tokens_text = self.tokenizer.tokenize(text)
                # 加上截断策略
                if len(tokens_text) > self.field_config.max_seq_len - 2:
                    tokens_text = truncation_words(tokens_text, self.field_config.max_seq_len - 2,
                                                   self.field_config.truncation_type)
                tokens = []
                tokens.append("[CLS]")
                for token in tokens_text:
                    tokens.append(token)
                tokens.append("[SEP]")
                src_id = self.tokenizer.convert_tokens_to_ids(tokens)
            else:
                if isinstance(text, str):
                    src_id = text.split(" ")
                src_id = [int(i) for i in text]
                if len(src_id) > self.field_config.max_seq_len - 2:
                    src_id = truncation_words(src_id, self.field_config.max_seq_len - 2,
                                              self.field_config.truncation_type)
                src_id.insert(0, self.tokenizer.covert_token_to_id("[CLS]"))
                src_id.append(self.tokenizer.covert_token_to_id("[SEP]"))

            src_ids.append(src_id)
            pos_id = list(range(len(src_id)))
            task_id = [0] * len(src_id)
            sentence_id = [0] * len(src_id)
            position_ids.append(pos_id)
            task_ids.append(task_id)
            sentence_ids.append(sentence_id)

        return_list = []
        padded_ids, input_mask, batch_seq_lens = pad_batch_data(src_ids,
                                                                pad_idx=self.field_config.padding_id,
                                                                return_input_mask=True,
                                                                return_seq_lens=True)
        sent_ids_batch = pad_batch_data(sentence_ids, pad_idx=self.field_config.padding_id)
        pos_ids_batch = pad_batch_data(position_ids, pad_idx=self.field_config.padding_id)
        task_ids_batch = pad_batch_data(task_ids, pad_idx=self.field_config.padding_id)

        return_list.append(padded_ids)  # append src_ids
        return_list.append(sent_ids_batch)  # append sent_ids
        return_list.append(pos_ids_batch)  # append pos_ids
        return_list.append(input_mask)  # append mask
        return_list.append(task_ids_batch)  # append task_ids
        return_list.append(batch_seq_lens)  # append seq_lens

        return return_list

    def structure_fields_dict(self, fields_id, start_index, need_emb=True):
        """静态图调用的方法，生成一个dict， dict有两个key:id , emb. id对应的是pyreader读出来的各个field产出的id，emb对应的是各个
        field对应的embedding
        :param fields_id: pyreader输出的完整的id序列
        :param start_index:当前需要处理的field在field_id_list中的起始位置
        :param need_emb:是否需要embedding（预测过程中是不需要embedding的）
        :return:
        """
        record_id_dict = {}
        record_id_dict[InstanceName.SRC_IDS] = fields_id[start_index]
        record_id_dict[InstanceName.SENTENCE_IDS] = fields_id[start_index + 1]
        record_id_dict[InstanceName.POS_IDS] = fields_id[start_index + 2]
        record_id_dict[InstanceName.MASK_IDS] = fields_id[start_index + 3]
        record_id_dict[InstanceName.TASK_IDS] = fields_id[start_index + 4]
        record_id_dict[InstanceName.SEQ_LENS] = fields_id[start_index + 5]

        record_emb_dict = None
        if need_emb and self.token_embedding:
            record_emb_dict = self.token_embedding.get_token_embedding(record_id_dict)

        record_dict = {}
        record_dict[InstanceName.RECORD_ID] = record_id_dict
        record_dict[InstanceName.RECORD_EMB] = record_emb_dict

        return record_dict

    def get_field_length(self):
        """获取当前这个field在进行了序列化之后，在field_id_list中占多少长度
        :return:
        """
        return FieldLength.ERNIE_TEXT_FIELD
