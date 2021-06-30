# -*- coding: utf-8 -*
"""
Erniexx Language Model
"""
import collections

from senta.common.register import RegisterSet
from senta.common.rule import InstanceName
from senta.models.model import Model
from senta.modules.ernie import ErnieModel


@RegisterSet.models.register
class RobertaLM(Model):
    """RobertaLM"""

    def __init__(self, model_params, args, task_group):
        # tricky code because base class Model need dict as first parameter
        model_params.print_config()
        self.task_group = task_group

        super(RobertaLM, self).__init__(model_params)
        self.args = args
        self.scheduled_lr = None
        self.loss_scaling = None

    def forward(self, fields_dict, phase):
        """
        forward calculate
        """
        src_ids = fields_dict['src_ids']
        pos_ids = fields_dict['pos_ids']
        sent_ids = fields_dict['sent_ids']
        task_ids = fields_dict['task_ids']
        input_mask = fields_dict['input_mask']
        mask_label = fields_dict['mask_label']
        mask_pos = fields_dict['mask_pos']
        lm_weight = fields_dict['lm_weight']

        pretrain_ernie = ErnieModel(
            src_ids=src_ids,
            position_ids=pos_ids,
            sentence_ids=sent_ids,
            task_ids=task_ids,
            input_mask=input_mask,
            config=self.model_params,
            weight_sharing=self.args.weight_sharing,
            use_fp16=self.args.use_fp16)

        result = collections.OrderedDict()

        mask_lm_loss = pretrain_ernie.get_lm_output(mask_label, mask_pos)
        total_loss = mask_lm_loss * lm_weight

        result['mask_lm_loss'] = mask_lm_loss
        result['lm_weight'] = lm_weight

        result[InstanceName.LOSS] = total_loss
        return result

    def optimizer(self, loss, is_fleet=False):
        """
        optimizer
        """
        optimizer_output_dict = collections.OrderedDict()
        optimizer_output_dict['use_ernie_opt'] = True

        opt_args_dict = collections.OrderedDict()
        opt_args_dict["loss"] = loss
        opt_args_dict["warmup_steps"] = self.args.warmup_steps
        opt_args_dict["num_train_steps"] = self.args.num_train_steps
        opt_args_dict["learning_rate"] = self.args.learning_rate
        opt_args_dict["weight_decay"] = self.args.weight_decay
        opt_args_dict["scheduler"] = self.args.lr_scheduler
        opt_args_dict["use_fp16"] = self.args.use_fp16
        opt_args_dict["use_dynamic_loss_scaling"] = self.args.use_dynamic_loss_scaling
        opt_args_dict["init_loss_scaling"] = self.args.init_loss_scaling
        opt_args_dict["incr_every_n_steps"] = self.args.incr_every_n_steps
        opt_args_dict["decr_every_n_nan_or_inf"] = self.args.decr_every_n_nan_or_inf
        opt_args_dict["incr_ratio"] = self.args.incr_ratio
        opt_args_dict["decr_ratio"] = self.args.decr_ratio

        optimizer_output_dict["opt_args"] = opt_args_dict

        return optimizer_output_dict
