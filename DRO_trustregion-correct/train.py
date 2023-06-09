import torch
from torch.utils.data import DataLoader
import numpy as np
import torch.nn as nn
import argparse
from dataset import AgeDataset
from network import AgeNet
from utils import *
from PIL import Image

def make_args():
    parser = argparse.ArgumentParser(description='argument parser')
    parser.add_argument('--epoch',default=100,type=int)
    parser.add_argument('--batch_size',default=32,type=int)
    parser.add_argument('--train_path',default=r'D:\xch2023\Optimization for RL\code\Ordinal-Regression-for-Age-Estimation\tarball\AFAD-Full')
    parser.add_argument('--val_path',default=r'D:\xch2023\Optimization for RL\code\Ordinal-Regression-for-Age-Estimation\tarball\AFAD-Full')
    parser.add_argument('--trained_model',default=None,help='the path to the saved trained model')
    parser.add_argument('--lr',default=1e-2,type=float)
    parser.add_argument('--save_path',default=r'D:\xch2023\Optimization for RL\code\Ordinal-Regression-for-Age-Estimation\results')
    args = parser.parse_args()
    return args

def train_loop(model,loader,optimizer,loss_func,device,importance):
    total = len(loader.dataset)
    importance = importance.to(device)
    for step,batch in enumerate(loader):
        x,label,age = batch
        x = x.to(device)
        label = label.to(device)
        age = age.to(device)
        predict = model(x)
        # print(predict.shape)
        loss = loss_func(predict,label,importance).to(device)

        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
        mae = MAE(predict,age)
        if step % 400 == 0:
            print('training || loss:{:.7f} MAE:{:.5f} [{}/{}]'.format(loss.item(),mae,len(x)*(step+1),total))

def val_loop(model,loader,device):
    total = len(loader.dataset)
    mae = 0
    for step,batch in enumerate(loader):
        x,label,age = batch
        x = x.to(device)
        label = label.to(device)
        age = age.to(device)
        predict = model(x)
        mae += MAE(predict,age)*len(age)
    mae = mae/total
    print('validate|| MAE:{:.5f}'.format(mae))
    return mae

def main(args):
    # images = []
    # train_filenames=r'tarball\AFAD-Full\15\111'
    # for fname in train_filenames:
    #     print(fname)
    #     print('1')
    #     images.append(np.array(Image.open(fname)))
    # train = np.array(images)
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    print(f'Using [{device}] for the work')
    
    # torch.cuda.manual_seed_all(2000)
    model = AgeNet()
    if args.trained_model is not None:
        dict = torch.load(args.trained_model)
        model.load_state_dict(dict)
        print('model loaded successfully!')
    else:
        print('train from scratch!')
    model.to(device)

    train_dataset = AgeDataset(args.train_path,train=True)
    val_dataset = AgeDataset(args.val_path)

    train_loader = DataLoader(train_dataset,batch_size=args.batch_size,shuffle=False)
    # train_loader = DataLoader(train_dataset,batch_size=args.batch_size,shuffle=True)
    val_loader = DataLoader(val_dataset,batch_size=args.batch_size)

    optimizer = torch.optim.SGD(model.parameters(),lr=args.lr,weight_decay=0.0001,momentum=0.9)
    scheduler = torch.optim.lr_scheduler.StepLR(optimizer,30,gamma=0.5,last_epoch=-1,verbose=False)

    importance = make_task_importance(args.train_path)

    best_MAE = 75+1. - 15. 
    is_best = 0
    for i in range(args.epoch):
        print('-----------------------epoch {}-----------------------'.format(i+1))
        print('-----------current learning rate: {:.6f}-----------'.format(optimizer.state_dict()['param_groups'][0]['lr']))
        model.train()
        train_loop(model,train_loader,optimizer,importance_cross_entropy,device,importance)
        with torch.no_grad():
            model.eval()
            mae = val_loop(model,val_loader,device)
        if mae < best_MAE:
            best_MAE = mae
            is_best = 1
        save_model(model,args,'epoch_{}.pth'.format(i+1),is_best)
        # if (i+1) % 5 == 0 and not is_best:
        #     dict = torch.load('E:\PKU\cv_learning\ordinal-regression\model\\best.pth')
        #     model.load_state_dict(dict)
        #     print('early stop and go back')
        scheduler.step()
        is_best = 0
        


if __name__ == '__main__':
    args = make_args()
    main(args)