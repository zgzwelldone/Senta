# -*- coding: utf-8 -*
"""
:py:class:`CustomFluidTokenEmbedding`
"""
from paddle import fluid

from senta.common.rule import InstanceName
from senta.modules.token_embedding.base_token_embedding import BaseTokenEmbedding


class CustomFluidTokenEmbedding(BaseTokenEmbedding):
    """CustomFluidTokenEmbedding: 使用paddle.fluid 的api实现的embedding，随机初始化，训练过程中不断finetune
    """

    def __init__(self, emb_dim, vocab_size):
        BaseTokenEmbedding.__init__(self, emb_dim, vocab_size)
        self.params_name = None

    def build(self):
        """
        添加一些自顶一个初始化信息，如参数名称
        :return:
        """
        pass

    def get_token_embedding(self, tokens_dict):
        """
        :param tokens_dict:
        :return:
        """
        tokens = tokens_dict[InstanceName.SRC_IDS]
        tokens_length = tokens_dict[InstanceName.SEQ_LENS]
        unpad_data = fluid.layers.sequence_unpad(tokens, length=tokens_length)
        emb = fluid.layers.embedding(input=unpad_data, size=[self.vocab_size, self.emb_dim])
        emb_dict = {
            InstanceName.SEQUENCE_EMB: emb,
            InstanceName.POOLED_EMB: None
        }
        return emb_dict

    def get_output_dim(self):
        """
        :return:
        """
        return self.emb_dim
