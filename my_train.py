import torch
import csv
from torch.utils.data import DataLoader
import torch.nn as nn
import argparse
from dataset import AgeDataset
# from network import AgeNet
from utils import *
from torchvision.models import resnet18
from pydrsom.pydrsom.drsom import DRSOMB as DRSOM
from pydrsom.pydrsom.drsom_utils import *
import matplotlib.pyplot as plt

def make_args():
    parser = argparse.ArgumentParser(description='argument parser')
    parser.add_argument("--optim",
                    required=False,
                    type=str,
                    default='drsom',
                    choices=[
                      'adam',
                      'sgd', 'sgd4',
                      'sgd2', 'sgd3',
                      'drsom',
                    ])
    parser.add_argument('--epoch',default=15,type=int)
    parser.add_argument('--batch_size',default=32,type=int)
    parser.add_argument('--train_path',default=r'D:\xch2023\Optimization for RL\code\Ordinal-Regression-for-Age-Estimation\tarball\AFAD-Full')
    parser.add_argument('--val_path',default=r'D:\xch2023\Optimization for RL\code\Ordinal-Regression-for-Age-Estimation\tarball\AFAD-Full')
    parser.add_argument('--trained_model',default=None,help='the path to the saved trained model')
    parser.add_argument('--lr',default=1e-3,type=float)
    parser.add_argument('--save_path',default=r'D:\xch2023\Optimization for RL\code\Ordinal-Regression-for-Age-Estimation\results')
    parser.add_argument('--out_dim',default=1)
    add_parser_options(parser)
    args = parser.parse_args()
    return args

def train_loop(model,loader,optimizer,loss_func,device,importance):
    total = len(loader.dataset)
    importance = importance.to(device)
    avg_loss=0;amount=100;avg_mae=0
    for step,batch in enumerate(loader):
        x,label,age = batch
        x = x.to(device)
        label = label.to(device)
        age = age.to(device)
        def closure(backward=True):
            optimizer.zero_grad()
            predict = model(x)
            loss = loss_func(predict, label,importance,0.1)
            loss.float()
            if not backward:
                return loss
            if DRSOM_MODE_QP == 0 or DRSOM_VERBOSE == 1:
                # only need for hvp
                loss.backward(create_graph=True)
            else:
                loss.backward()
            return loss, predict   
        if args.optim=='drsom':
            loss,predict= optimizer.step(closure=closure)
        else:
            predict = model(x)
            predict_real=predict*75
            loss = loss_func(predict,label,importance,0.1).to(device)
            loss.float()
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
        predict_real=predict*75
        # print(predict_real[0:10])
        # print(age[0:10])
        mae = MAE(predict_real,age)
        avg_loss+=loss.item()
        avg_mae+=mae
        if step % 100 == 0:
            print('training || loss:{:.7f} MAE:{:.5f} [{}/{}]'.format(loss.item(),mae,len(x)*(step+1),total))
        if step>amount:
            avg_loss=avg_loss/amount
            avg_mae=avg_mae/amount
            break
    return avg_loss,avg_mae

def val_loop(model,loader,device):
    total = len(loader.dataset)
    amount=20
    mae = 0
    for step,batch in enumerate(loader):
        if step < amount:
            x,label,age = batch
            x = x.to(device)
            label = label.to(device)
            age = age.to(device)
            predict = model(x)
            mae += MAE(predict,age)*len(age)
        else:
            break
    mae = mae/(amount*len(age))
    print('validate|| MAE:{:.5f}'.format(mae))
    return mae
# resnet model
def get_model(out_dim):
    model=resnet18(pretrained=False)
    fc_features=model.fc.in_features
    model.fc=nn.Linear(fc_features,out_dim)
    return model

# def get_eta(inner_loss,lbda,init_eta=0,lr=0.01):
#     eta=init_eta
#     iter=0
#     # objective=lbda*(-1+1/4*(max(0,inner_loss/lbda-eta+2))^2)+eta
#     gradient=1-lbda*(max(0,inner_loss/lbda-eta+2))/2
#     if gradient>1e-6:
#         eta=eta-lr*gradient
#         print(iter)
#         iter+=1
#     else:
#         return eta

def main(args):
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    print(f'Using [{device}] for the work')
    
    # torch.cuda.manual_seed_all(2000)
    model = get_model(args.out_dim)
    if args.trained_model is not None:
        dict = torch.load(args.trained_model)
        model.load_state_dict(dict)
        print('model loaded successfully!')
    else:
        print('train from scratch!')
    model.to(device)

    train_dataset = AgeDataset(args.train_path,train=True)
    val_dataset = AgeDataset(args.val_path)

    train_loader = DataLoader(train_dataset,batch_size=args.batch_size,shuffle=True)
    val_loader = DataLoader(val_dataset,batch_size=args.batch_size)

    if args.optim=='drsom':
        func_kwargs=render_args(args)
        optimizer = DRSOM(model.parameters(),**func_kwargs)
    else:
        optimizer = torch.optim.SGD(model.parameters(),lr=args.lr,weight_decay=0.0001,momentum=0.9)
        scheduler = torch.optim.lr_scheduler.StepLR(optimizer,30,gamma=0.5,last_epoch=-1,verbose=False)

    importance = make_task_importance(args.train_path)

    best_MAE = 72. - 15. 
    is_best = 0
    all_avg_loss=[];all_avg_mae=[];all_val_mae=[]
    for i in range(args.epoch):
        print('-----------------------epoch {}-----------------------'.format(i+1))
        if args.optim=='sgd':
            print('-----------current learning rate: {:.6f}-----------'.format(optimizer.state_dict()['param_groups'][0]['lr']))
        model.train()
        # train_loop(model,train_loader,optimizer,importance_cross_entropy,device,importance)
        avg_loss,avg_mae=train_loop(model,train_loader,optimizer,DRO_MSE,device,importance)
        # with torch.no_grad():
        #     model.eval()
        #     mae_val = val_loop(model,val_loader,device)
        # if mae_val < best_MAE:
        #     best_MAE = mae_val
        #     is_best = 1
        save_model(model,args,'epoch_{}.pth'.format(i+1),is_best)
        # if (i+1) % 5 == 0 and not is_best:
        #     dict = torch.load('E:\PKU\cv_learning\ordinal-regression\model\\best.pth')
        #     model.load_state_dict(dict)
        #     print('early stop and go back')
        if args.optim=='sgd':
            scheduler.step()
        is_best = 0
        all_avg_loss.append(avg_loss)
        all_avg_mae.append(avg_mae.item())
        # all_val_mae.append(mae_val.item())
    header = ['all_avg_loss', 'all_avg_mae', 'all_val_mae']
    # data=[all_avg_loss,all_avg_mae,all_val_mae]
    with open('drsom.csv', 'w', encoding='utf-8', newline='') as file_obj:
    # 创建writer对象
        writer = csv.writer(file_obj)
        # 写表头
        writer.writerow(header)
        # 一次写入多行
        for i in range(args.epoch):
            writer.writerow((all_avg_loss[i],all_avg_mae[i]))

    # plt.figure(dpi=300,figsize=(8,4))
    # plt.title('Result on PointENV')
    # plt.plot(np.arange(1, epsoids + 1), vpg_1[col_name], label='pure pg, a=1e-2')
    # plt.plot(np.arange(1, epsoids + 1), vpg_2[col_name], label='pure pg, a=1e-1')
    # plt.legend()
    # plt.ylabel('AVGReturn')
    # plt.xlabel('Episode #')
    # plt.savefig('PointENV_result.jpg')
    # plt.show()
        


if __name__ == '__main__':
    args = make_args()
    main(args)