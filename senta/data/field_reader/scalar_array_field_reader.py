# -*- coding: utf-8 -*
"""
:py:class:`ScalarArrayFieldReader`

"""
from senta.common.register import RegisterSet
from senta.common.rule import DataShape, FieldLength, InstanceName
from senta.data.field_reader.base_field_reader import BaseFieldReader
from senta.data.tokenizer.custom_tokenizer import CustomTokenizer
from senta.data.util_helper import pad_batch_data
from senta.utils.util_helper import truncation_words


@RegisterSet.field_reader.register
class ScalarArrayFieldReader(BaseFieldReader):
    """标量数组的field_reader，直接返回数据本身(数据可以是明文字符串，明文通过json文件中配置的vocab_path去进行转换)和数据长度
     直接以空格分隔 备注：数据是加了padding的。
    """

    def __init__(self, field_config):
        """
        :param field_config:
        """
        BaseFieldReader.__init__(self, field_config=field_config)
        self.paddle_version_code = 1.6
        if field_config.vocab_path and field_config.need_convert:
            self.tokenizer = CustomTokenizer(vocab_file=self.field_config.vocab_path)

    def init_reader(self):
        """ 初始化reader格式
        :return: reader的shape[]、type[]、level[]
        """
        shape = [[-1, self.field_config.max_seq_len, 1], [-1]]
        levels = [0, 0]

        if self.field_config.data_type == DataShape.INT:
            types = ['int64']

        elif self.field_config.data_type == DataShape.FLOAT:
            types = ['float32']
        else:
            raise TypeError("ScalarArrayFieldReader's data_type must be int or float")
        """seq_length"""
        types.append('int64')
        return shape, types, levels

    def convert_texts_to_ids(self, batch_text):
        """ 明文序列化
        :return: id_list
        """
        src_ids = []
        for text in batch_text:
            if self.tokenizer and self.field_config.need_convert:
                tokens = self.tokenizer.tokenize(text)
                src_id = self.tokenizer.convert_tokens_to_ids(tokens)
            else:
                src_id = text.split(" ")

            # 加上截断策略
            if len(src_id) > self.field_config.max_seq_len:
                src_id = truncation_words(src_id, self.field_config.max_seq_len, self.field_config.truncation_type)
            src_ids.append(src_id)

        data_type = "int64" if self.field_config.data_type == DataShape.INT else "float32"

        padded_ids, batch_seq_lens = pad_batch_data(src_ids, insts_data_type=data_type,
                                                    pad_idx=self.field_config.padding_id,
                                                    return_input_mask=False,
                                                    return_seq_lens=True)
        return_list = []
        return_list.append(padded_ids)
        return_list.append(batch_seq_lens)
        return return_list

    def get_field_length(self):
        """获取当前这个field在进行了序列化之后，在field_id_list中占多少长度
        :return:
        """
        return FieldLength.ARRAY_SCALAR_FIELD

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
        record_id_dict[InstanceName.SEQ_LENS] = fields_id[start_index + 1]
        record_dict = {}
        record_dict[InstanceName.RECORD_ID] = record_id_dict
        record_dict[InstanceName.RECORD_EMB] = None

        return record_dict
