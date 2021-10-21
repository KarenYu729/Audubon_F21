# wandb_train.py
#
# Utilize wandb
#
# Authors: Krish Kabra, Minxuan Luo, Alexander Xiong, William Lu
# Copyright (C) 2021-2022 Houston Audubon and others

import numpy as np
import os
import matplotlib.pyplot as plt
import wandb
from datetime import datetime

from detectron2.engine import DefaultPredictor, default_argument_parser, launch
from detectron2.utils.logger import setup_logger
from detectron2.data import build_detection_test_loader
from detectron2.evaluation import COCOEvaluator, inference_on_dataset

from utils.config import add_retinanet_config, add_fasterrcnn_config
from utils.dataloader import register_datasets
from utils.trainer import WAndBTrainer

def get_parser():
    parser = default_argument_parser() #  Create a parser with some common arguments used by detectron2 users.
    # directory management
    parser.add_argument('--data_dir',default='./data',type=str, help="path to dataset directory. must contain 'train', 'val', and 'test' folders")
    parser.add_argument('--img_ext',default='.JPEG',type=str, help="image file extension")
    parser.add_argument('--dir_exceptions',default=[],type=list, help="list of folders in dataset directory to be ignored")
    # model
    parser.add_argument('--model_type',default='retinanet',type=str,help='choice of object detector. Options: "retinanet", "faster-rcnn"')
    parser.add_argument('--model_config_file',default="COCO-Detection/retinanet_R_50_FPN_1x.yaml",type=str,help='path to model config file eg. "COCO-Detection/retinanet_R_50_FPN_1x.yaml"')
    parser.add_argument('--pretrained_coco_model_weights',default=True,type=bool,help='load pretrained coco model weights from model config file')
    parser.add_argument('--num_workers', default=4, type=int, help='number of workers for dataloader')
    parser.add_argument('--eval_period', default=0, type=int, help='period between coco eval scores on val set')
    parser.add_argument('--max_iter', default=1000, type=int, help='maximum iterations')
    # hyperparams
    parser.add_argument('--learning_rate',default=1e-3,type=float,help='base learning rate')
    parser.add_argument('--solver_warmup_factor', type=float, default=0.001, help='warmup factor used for warmup stage of scheduler')
    parser.add_argument('--solver_warmup_iters', type=int, default=100, help='iterations for warmup stage of scheduler')
    parser.add_argument('--scheduler_gamma', type=float, default=0.1,help='gamma decay factor used in lr scheduler')
    parser.add_argument('--scheduler_steps', type=list, default=(1000,), help='list containing lr scheduler iteration steps')
    parser.add_argument('--weight_decay', type=float, default=1e-4, help='L2 regularization')
    parser.add_argument('--batch_size', default=8, type=int, help='batch size')
    parser.add_argument('--focal_loss_gamma',default=2.0,type=float,help='focal loss gamma (only for retinanet)')
    parser.add_argument('--focal_loss_alpha',default=0.25,type=float,help='focal loss alpha (only for retinanet)')

    parser.add_argument('--output_dir',default='./output/wandb/',type=str,help='output directory for training logs and final model')

    return parser

def setup(args):
    # data setup
    data_dir = args.data_dir
    img_ext = args.img_ext
    dir_exceptions = args.dir_exceptions
    dirs = [os.path.join(data_dir,d) for d in os.listdir(data_dir)
            if d not in dir_exceptions]
    register_datasets(dirs,img_ext)

    # Create detectron2 config
    if args.model_type == 'retinanet':
        cfg = add_retinanet_config(args)
        cfg.MODEL.RETINANET.NUM_CLASSES = 1
    elif args.model_type == 'faster-rcnn':
        cfg = add_fasterrcnn_config(args)
        cfg.MODEL.ROI_HEADS.NUM_CLASSES = 1
    else:
        raise Exception("Invalid model type entered")

    # cfg.OUTPUT_DIR = os.path.join(args.output_dir, f"{args.model_type}-{datetime.now().strftime('%Y%m%d-%H%M%S')}")
    cfg.OUTPUT_DIR = args.output_dir
    os.makedirs(cfg.OUTPUT_DIR, exist_ok=True)

    return cfg

def train(cfg):
    # setup training logger
    setup_logger()

    cfg.DATASETS.TRAIN = ("birds_only_train",)
    cfg.DATASETS.TEST = ("birds_only_val",)
    cfg.INPUT.MIN_SIZE_TRAIN = (640,)
    cfg.INPUT.MIN_SIZE_TEST = (640,)

    trainer = WAndBTrainer(cfg)
    trainer.resume_or_load(resume=False)

    return trainer.train()

def eval(cfg):
    # load model weights
    cfg.MODEL.WEIGHTS = os.path.join(cfg.OUTPUT_DIR, "model_final.pth")  # path to the model we just trained
    predictor = DefaultPredictor(cfg)

    cfg.DATASETS.TEST = ("birds_only_test")

    test_evaluator = COCOEvaluator("birds_only_test", output_dir=cfg.OUTPUT_DIR)
    test_loader = build_detection_test_loader(cfg, "birds_only_test")
    print('test inference:', inference_on_dataset(predictor.model, test_loader, test_evaluator))

def main(args):
    cfg = setup(args)
    train(cfg)
    eval(cfg)

if __name__ == "__main__":
    args = get_parser().parse_args()

    wandb.init(project='audubon_f21')
    wandb.config.update(args)

    print("Command Line Args:", args)
    launch(
        main,
        args.num_gpus,
        num_machines=args.num_machines,
        machine_rank=args.machine_rank,
        dist_url=args.dist_url,
        args=(args,)
    )