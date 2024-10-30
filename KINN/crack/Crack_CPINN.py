# 这里用里兹的方法研究裂纹问题，两个特解网络，不用可能位移场，突出
import numpy as np
import torch
import matplotlib.pyplot as plt
from  torch.autograd import grad
import time
from itertools import chain

def setup_seed(seed):
# random seed
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    np.random.seed(seed)
    torch.backends.cudnn.deterministic = True
setup_seed(2024)

penalty = 1
delta = 0.0
train_p = 0
nepoch_u0 = 2500 
a = 1

def interface(Ni):
    '''
     生成交界面的随机点
    '''
    re = np.random.rand(Ni)
    theta = 0
    x = np.cos(theta) * re
    y = np.sin(theta) * re
    xi = np.stack([x, y], 1)
    xi = xi.astype(np.float32)
    xi = torch.tensor(xi,  requires_grad=True, device='cuda')
    return xi
def train_data(Nb, Nf):
    '''
    生成强制边界点，四周以及裂纹处
    生成上下的内部点
    '''
    

    xu = np.hstack([np.random.rand(int(Nb/4),1)*2-1,  np.ones([int(Nb/4),1])]).astype(np.float32)
    xd = np.hstack([np.random.rand(int(Nb/4),1)*2-1,  -np.ones([int(Nb/4),1])]).astype(np.float32)
    xl = np.hstack([-np.ones([int(Nb/4),1]), np.random.rand(int(Nb/4),1)*2-1]).astype(np.float32)
    xr = np.hstack([np.ones([int(Nb/4),1]), np.random.rand(int(Nb/4),1)*2-1]).astype(np.float32)
    xcrack = np.hstack([-np.random.rand(int(Nb/4),1), np.zeros([int(Nb/4),1])]).astype(np.float32)
    # 随机撒点时候，边界没有角点，这里要加上角点
    xc1 = np.array([[-1., 1.], [1., 1.], [1., -1.], [-1., -1.]], dtype=np.float32) # 边界点效果不好，增加训练点
    xc2 = np.array([[-1., 1.], [1., 1.], [1., -1.], [-1., -1.]], dtype=np.float32)
    xc3 = np.array([[-1., 1.], [1., 1.], [1., -1.], [-1., -1.]], dtype=np.float32)
    Xb = np.concatenate((xu, xd, xl, xr, xcrack, xc1, xc2, xc3)) # 上下左右四个边界组装起来

    Xb = torch.tensor(Xb, device='cuda') # 转化成tensor
    
    Xf = torch.rand(Nf, 2)*2-1
    

    Xf1 = Xf[(Xf[:, 1]>0) & (torch.norm(Xf, dim=1)>=delta)] # 上区域点，去除内部多配的点
    Xf2 = Xf[(Xf[:, 1]<0) & (torch.norm(Xf, dim=1)>=delta)]  # 下区域点，去除内部多配的点
    
    Xf1 = torch.tensor(Xf1, requires_grad=True, device='cuda')
    Xf2 = torch.tensor(Xf2, requires_grad=True, device='cuda')
    
    return Xb, Xf1, Xf2

# for particular solution 
class particular(torch.nn.Module):
    def __init__(self, D_in, H, D_out):
        """
        In the constructor we instantiate two nn.Linear modules and assign them as
        member variables.
        """
        super(particular, self).__init__()
        self.linear1 = torch.nn.Linear(D_in, H)
        self.linear2 = torch.nn.Linear(H, H)
        self.linear3 = torch.nn.Linear(H, H)
        self.linear4 = torch.nn.Linear(H, H)
        self.linear5 = torch.nn.Linear(H, D_out)
        
        
#        self.trans = torch.nn.Linear(1, H)
        # self.a1 = torch.nn.Parameter(torch.Tensor([0.2]))
        

        self.a1 = torch.nn.Parameter(torch.Tensor([0.1])).cuda()
        self.a2 = torch.Tensor([0.1])
        self.a3 = torch.Tensor([0.1])
        self.n = 1/self.a1.data
        
        self.fre1 = torch.ones(25).cuda()
        self.fre2 = torch.ones(25).cuda()
        self.fre3 = torch.ones(25).cuda()
        self.fre4 = torch.ones(25).cuda()
        self.fre5 = torch.ones(25).cuda()
        self.fre6 = torch.ones(25).cuda()
        self.fre7 = torch.ones(25).cuda()
        self.fre8 = torch.ones(25).cuda()
        
        torch.nn.init.normal_(self.linear1.bias, mean=0, std=1)
        torch.nn.init.normal_(self.linear2.bias, mean=0, std=1)
        torch.nn.init.normal_(self.linear3.bias, mean=0, std=1)
        torch.nn.init.normal_(self.linear4.bias, mean=0, std=1)
        torch.nn.init.normal_(self.linear5.bias, mean=0, std=1)

        torch.nn.init.normal_(self.fre1, mean=0, std=a)
        torch.nn.init.normal_(self.fre2, mean=0, std=a*2)
        torch.nn.init.normal_(self.fre1, mean=0, std=a*3)
        torch.nn.init.normal_(self.fre2, mean=0, std=a*4)
        torch.nn.init.normal_(self.fre1, mean=0, std=a*5)
        torch.nn.init.normal_(self.fre2, mean=0, std=a*6)
        torch.nn.init.normal_(self.fre1, mean=0, std=a*7)
        torch.nn.init.normal_(self.fre2, mean=0, std=a*8)
        
        torch.nn.init.normal_(self.linear1.weight, mean=0, std=np.sqrt(2/(D_in+H)))
        torch.nn.init.normal_(self.linear2.weight, mean=0, std=np.sqrt(2/(H+H)))
        torch.nn.init.normal_(self.linear3.weight, mean=0, std=np.sqrt(2/(H+H)))
        torch.nn.init.normal_(self.linear4.weight, mean=0, std=np.sqrt(2/(H+H)))
        torch.nn.init.normal_(self.linear5.weight, mean=0, std=np.sqrt(2/(H+D_out)))

    def forward(self, x):
        """
        In the forward function we accept a Tensor of input data and we must return
        a Tensor of output data. We can use Modules defined in the constructor as
        well as arbitrary operators on Tensors.
        """
        #特征变换
        # yt1 = torch.cat((torch.cos(self.fre1*x[:, 0].unsqueeze(1)), torch.sin(self.fre1*x[:, 0].unsqueeze(1))), 1)
        # yt2 = torch.cat((torch.cos(self.fre2*x[:, 0].unsqueeze(1)), torch.sin(self.fre2*x[:, 0].unsqueeze(1))), 1)
        # yt3 = torch.cat((torch.cos(self.fre3*x[:, 1].unsqueeze(1)), torch.sin(self.fre3*x[:, 1].unsqueeze(1))), 1)
        # yt4 = torch.cat((torch.cos(self.fre4*x[:, 1].unsqueeze(1)), torch.sin(self.fre4*x[:, 1].unsqueeze(1))), 1)      
        # yt5 = torch.cat((torch.cos(self.fre5*x[:, 1].unsqueeze(1)), torch.sin(self.fre5*x[:, 1].unsqueeze(1))), 1)
        # yt6 = torch.cat((torch.cos(self.fre6*x[:, 1].unsqueeze(1)), torch.sin(self.fre6*x[:, 1].unsqueeze(1))), 1)        
        # yt7 = torch.cat((torch.cos(self.fre7*x[:, 1].unsqueeze(1)), torch.sin(self.fre7*x[:, 1].unsqueeze(1))), 1)
        # yt8 = torch.cat((torch.cos(self.fre8*x[:, 1].unsqueeze(1)), torch.sin(self.fre8*x[:, 1].unsqueeze(1))), 1)        
        # yt = torch.cat((yt1, yt2, yt3, yt4, yt5, yt6, yt7, yt8), 1)
        yt = x
        y1 = torch.tanh(self.n*self.a1*self.linear1(yt))
        y2 = torch.tanh(self.n*self.a1*self.linear2(y1))
        y3 = torch.tanh(self.n*self.a1*self.linear3(y2)) + y1
        y4 = torch.tanh(self.n*self.a1*self.linear4(y3)) + y2
        y =  self.linear5(y4)
        return y


    
def pred(xy):
    '''
    

    Parameters
    ----------
    Nb : int
        the  number of boundary point.
    Nf : int
        the  number of internal point.

    Returns
    -------
    Xb : tensor
        The boundary points coordinates.
    Xf1 : tensor
        interior hole.
    Xf2 : tensor
        exterior region.
    '''
    pred = torch.zeros((len(xy), 1), device = 'cuda')
    # 上区域的预测，由于要用到不同的特解网络
    pred[(xy[:, 1]>0) ] = model_p1(xy[xy[:, 1]>0])
    # 下区域的预测，由于要用到不同的特解网络
    pred[xy[:, 1]<0] = model_p2(xy[xy[:, 1]<0])
    #  on the interface (crack)
    pred[(xy[:, 1]==0) & (xy[:, 0]>0)] = (model_p1(xy[(xy[:, 1]==0) & (xy[:, 0]>0)]) + model_p2(xy[(xy[:, 1]==0) & (xy[:, 0]>0)]))/2 
    return pred    
    
def evaluate():
    N_test = 100
    x = np.linspace(-1, 1, N_test).astype(np.float32)
    y = np.linspace(-1, 1, N_test).astype(np.float32)
    x, y = np.meshgrid(x, y)
    xy_test = np.stack((x.flatten(), y.flatten()),1)
    xy_test = torch.from_numpy(xy_test).cuda() # to the model for the prediction
    
    u_pred = pred(xy_test)
    u_pred = u_pred.data
    u_pred = u_pred.reshape(N_test, N_test).cpu()
    

    u_exact = np.zeros(x.shape)
    u_exact[y>0] = np.sqrt(np.sqrt(x[y>0]**2+y[y>0]**2))*np.sqrt((1-x[y>0]/np.sqrt(x[y>0]**2+y[y>0]**2))/2)
    u_exact[y<0] = -np.sqrt(np.sqrt(x[y<0]**2+y[y<0]**2))*np.sqrt((1-x[y<0]/np.sqrt(x[y<0]**2+y[y<0]**2))/2)

    u_exact = u_exact.reshape(x.shape)
    u_exact = torch.from_numpy(u_exact)
    error = torch.abs(u_pred - u_exact) # get the error in every points
    error_t = torch.norm(error)/torch.norm(u_exact) # get the total relative L2 error
    return error_t

# learning the homogenous network

model_p1 = particular(2, 30, 1).cuda()
model_p2 = particular(2, 30, 1).cuda()
criterion = torch.nn.MSELoss()
optim_h = torch.optim.Adam(params=chain(model_p1.parameters(), model_p2.parameters()), lr= 0.001)
scheduler = torch.optim.lr_scheduler.MultiStepLR(optim_h, milestones=[1000, 3000, 5000], gamma = 0.1)
loss_array = []
error_array = []
loss1_array = []
loss2_array = []    
lossi_array = []
nepoch_u0 = int(nepoch_u0)
start = time.time()
b1 = 1
b2 = 1
b3 = 50
b4 = 50
b5 = 10

for epoch in range(nepoch_u0):
    if epoch%1000==0:
        end = time.time()
        consume_time = end-start
        print('time is %f' % consume_time)
    if epoch%100 == 0:        
        Xb, Xf1, Xf2 = train_data(256, 4096)
        Xi = interface(1000)
        
        Xb1 = Xb[Xb[:, 1]>=0] # 上边界点
        Xb2 = Xb[Xb[:, 1]<=0] # 下边界点
        target_b1 = torch.sqrt(torch.sqrt(Xb1[:,0]**2+Xb1[:, 1]**2))*torch.sqrt((1-Xb1[:,0]/torch.sqrt(Xb1[:,0]**2+Xb1[:,1]**2))/2)
        target_b1 = target_b1.unsqueeze(1)
        target_b2 = -torch.sqrt(torch.sqrt(Xb2[:,0]**2+Xb2[:, 1]**2))*torch.sqrt((1-Xb2[:,0]/torch.sqrt(Xb2[:,0]**2+Xb2[:,1]**2))/2)
        target_b2 = target_b2.unsqueeze(1)
    def closure():  
        global b1,b2,b3,b4,b5
        u_pred1 = model_p1(Xf1)  
        u_pred2 = model_p2(Xf2) # 获得特解

        du1dxy = grad(u_pred1, Xf1, torch.ones(Xf1.size()[0], 1).cuda(), retain_graph=True, create_graph=True)[0]
        du1dx = du1dxy[:, 0].unsqueeze(1)
        du1dy = du1dxy[:, 1].unsqueeze(1)
        du1dxxy = grad(du1dx, Xf1, torch.ones(Xf1.size()[0], 1).cuda(), retain_graph=True, create_graph=True)[0]
        du1dyxy = grad(du1dy, Xf1, torch.ones(Xf1.size()[0], 1).cuda(), retain_graph=True, create_graph=True)[0]
        du1dxx = du1dxxy[:, 0].unsqueeze(1)
        du1dyy = du1dyxy[:, 1].unsqueeze(1)        
        
        du2dxy = grad(u_pred2, Xf2, torch.ones(Xf2.size()[0], 1).cuda(), retain_graph=True, create_graph=True)[0]
        du2dx = du2dxy[:, 0].unsqueeze(1)
        du2dy = du2dxy[:, 1].unsqueeze(1)
        du2dxxy = grad(du2dx, Xf2, torch.ones(Xf2.size()[0], 1).cuda(), retain_graph=True, create_graph=True)[0]
        du2dyxy = grad(du2dy, Xf2, torch.ones(Xf2.size()[0], 1).cuda(), retain_graph=True, create_graph=True)[0]
        du2dxx = du2dxxy[:, 0].unsqueeze(1)
        du2dyy = du2dyxy[:, 1].unsqueeze(1) 
        
        J1 = torch.sum((du1dxx + du1dyy)**2).mean()
        J2 = torch.sum((du2dxx + du2dyy)**2).mean()
        

        J = J1 + J2
        
        # 罚函数项，上下两个网络的本质边界的损失
        pred_b1 = model_p1(Xb1) # predict the boundary condition
        loss_b1 = criterion(pred_b1, target_b1)  
        pred_b2 = model_p2(Xb2) # predict the boundary condition
        loss_b2 = criterion(pred_b2, target_b2) 
        loss_b = loss_b1 + loss_b2# 边界的损失函数
        # 求交界面的损失函数，因为这里是两个特解网络
        pred_bi1 = model_p1(Xi) # predict the boundary condition
        pred_bi2 = model_p2(Xi) # predict the boundary condition
        loss_bi = criterion(pred_bi1, pred_bi2)  
        
        # 计算交界面的位移导数，由于是y=0的交界面，所以我们的导数的损失只要两个网络在y方向的导数相同即可
        du1dxyii = grad(pred_bi1, Xi, torch.ones(Xi.size()[0], 1).cuda(), retain_graph=True, create_graph=True)[0]
        du2dxyii = grad(pred_bi2, Xi, torch.ones(Xi.size()[0], 1).cuda(), retain_graph=True, create_graph=True)[0]     
        loss_bdi = criterion(du1dxyii[:, 1].unsqueeze(1), du2dxyii[:, 1].unsqueeze(1))   
        
        loss = b1 * J1 + b2 * J2 + b3 * loss_b1 + b4 * loss_b2  + b5 * (loss_bi+loss_bdi)
        error_t = evaluate()
        optim_h.zero_grad()
        loss.backward(retain_graph=True)
        loss_array.append(loss.data.cpu())
        error_array.append(error_t.data.cpu())
        if epoch%10==0:
            print(' epoch : %i, the loss : %f ,  J1 : %f , J2 : %f ,  Jb: %f, Ji: %f, error: %f' % \
                  (epoch, loss.data, J1.data, J2.data,  loss_b.data, (loss_bi+loss_bdi).data, error_t.data))# if epoch%100==0:
        return loss
    optim_h.step(closure)
    scheduler.step()
torch.save(model_p1, './model/CPINNs_MLP_penalty/CPINNs_MLP_penalty_up')
torch.save(model_p2, './model/CPINNs_MLP_penalty/CPINNs_MLP_penalty_down')  
    
np.save( './results/CPINNs_MLP_penalty/error.npy', np.array(error_array))

N_test = 100
x = np.linspace(-1, 1, N_test).astype(np.float32)
y = np.linspace(-1, 1, N_test).astype(np.float32)
x, y = np.meshgrid(x, y)
xy_test = np.stack((x.flatten(), y.flatten()),1)
xy_test = torch.from_numpy(xy_test).cuda() # to the model for the prediction
u_pred = pred(xy_test)
u_pred = u_pred.data
u_pred = u_pred.reshape(N_test, N_test).cpu()

u_exact = np.zeros(x.shape)
u_exact[y>0] = np.sqrt(np.sqrt(x[y>0]**2+y[y>0]**2))*np.sqrt((1-x[y>0]/np.sqrt(x[y>0]**2+y[y>0]**2))/2)
u_exact[y<0] = -np.sqrt(np.sqrt(x[y<0]**2+y[y<0]**2))*np.sqrt((1-x[y<0]/np.sqrt(x[y<0]**2+y[y<0]**2))/2)
u_exact = torch.from_numpy(u_exact)
error = torch.abs(u_pred - u_exact) # get the error in every points

# plot the prediction solution
fig = plt.figure(figsize=(20, 20))

plt.subplot(2, 3, 1)
h2 = plt.contourf(x, y, u_pred.detach().numpy(), levels=100 ,cmap = 'jet')
plt.title('penalty prediction') 
plt.colorbar(h2)

plt.subplot(2, 3, 2)
h3 = plt.contourf(x, y, u_exact, levels=100 ,cmap = 'jet')
plt.title('exact solution') 
plt.colorbar(h3)

plt.subplot(2, 3, 3)
h4 = plt.contourf(x, y, error.detach().numpy(), levels=100 ,cmap = 'jet')
plt.title('absolute error') 
plt.colorbar(h4)

plt.subplot(2, 3, 4)
loss_array = np.array(loss_array)
loss_array = loss_array[loss_array<50]
plt.yscale('log')
plt.plot(loss_array)
plt.xlabel('the iteration')
plt.ylabel('loss')
plt.title('loss evolution')
 
plt.subplot(2, 3, 5)
error_array = np.array(error_array)
error_array = error_array[error_array<1]
plt.yscale('log')
plt.plot(error_array)
plt.xlabel('the iteration')
plt.ylabel('error')
plt.title('relative total error evolution') 

plt.subplot(2, 3, 6)
N_test = 11
interx = torch.linspace(0, 1, N_test)[1:-1] # 获得interface的测试点
intery = torch.zeros(N_test)[1:-1]
inter = torch.stack((interx, intery),1)
inter = inter.requires_grad_(True).cuda() # 可以求导并且放入cuda中
pred_inter = pred(inter)
dudxyi = grad(pred_inter, inter, torch.ones(inter.size()[0], 1).cuda())[0]
dudyi = dudxyi[:, 1].unsqueeze(1) # 获得了交界面奇异应变
dudyi_e = 0.5/torch.sqrt(torch.norm(inter, dim=1))# 获得交界面的应变的精确值 

inter_strain = np.vstack([interx.cpu(), dudyi.detach().cpu().flatten()])
np.save( './results/CPINNs_MLP_penalty/interface.npy', inter_strain)

plt.plot(interx.cpu(), dudyi_e.detach().cpu(), label = 'exact')
plt.plot(interx.cpu(), dudyi.detach().cpu(), label = 'predict')
plt.xlabel('coordinate x')
plt.ylabel('strain e32')
plt.title('cpinn about e32 on interface')
plt.legend()

plt.suptitle("CPINNs_MLP_penalty")
plt.savefig('./results/CPINNs_MLP_penalty/CPINNs_MLP_penalty.pdf', dpi = 300)
plt.show()

# storage the error contouf  
h1 = plt.contourf(x, y, error.detach().numpy(), levels=100 ,cmap = 'jet')
ax = plt.gca()
ax.set_aspect(1)
plt.colorbar(h1).ax.set_title('abs error')
plt.xlabel('x')
plt.ylabel('y')
plt.savefig('./results/CPINNs_MLP_penalty/abs_error_CPINNs_MLP_penalty.pdf', dpi = 300)
plt.show()  



sum(p.numel() for p in model_p1.parameters())
sum(p.numel() for p in model_p2.parameters())

