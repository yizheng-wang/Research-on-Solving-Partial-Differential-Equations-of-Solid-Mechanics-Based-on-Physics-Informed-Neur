# comparision RBF and neural network to approximate the distance function
import numpy as np
import torch
import matplotlib.pyplot as plt
from sklearn.neighbors import KDTree
import time

torch.set_default_tensor_type(torch.DoubleTensor) # 将tensor的类型变成默认的double
torch.set_default_tensor_type(torch.cuda.DoubleTensor) # 将cuda的tensor的类型变成默认的double

def setup_seed(seed):
     torch.manual_seed(seed)
     torch.cuda.manual_seed_all(seed)
     np.random.seed(seed)
     #random.seed(seed)
     torch.backends.cudnn.deterministic = True
# 设置随机数种子
setup_seed(0)
# =============================================================================
# use RBF to approximate distance function
# =============================================================================

# learning the boundary solution
# step 1: get the boundary train data and target for boundary condition
# learning the distance neural network by RBF
def RBF(x):
    d_total_t = torch.from_numpy(d_total).unsqueeze(1) # d_total is the internal and boundary points
    w_t = torch.from_numpy(w) # weight of the RBF
    x_l = x.unsqueeze(0).repeat(len(d_total_t), 1, 1) # input 
    R = torch.norm(d_total_t - x_l, dim=2) # compute the distance between the reference and input points
    y = torch.mm(torch.exp(-gama*R.T), w_t) # get the output
    return y

n_d = 11 # the number of the points in each boundary.
n_dom = 11
gama = 0.5

n_test = 201
ep = np.linspace(-1, 1, n_test) # distribute points from -1 to 1 uniformly
# obtain 4 boundary points(for more accurate evaluation)
ep1 = np.zeros((n_test, 2)) # up
ep1[:, 0], ep1[:, 1] = ep, 1
ep2 = np.zeros((n_test, 2)) # down
ep2[:, 0], ep2[:, 1] = ep, -1
ep3 = np.zeros((n_test, 2)) # left
ep3[:, 0], ep3[:, 1] = -1, ep
ep4 = np.zeros((n_test, 2)) # right
ep4[:, 0], ep4[:, 1] = 1, ep
ep5 = np.zeros((n_test, 2)) # center
ep5[:, 0], ep5[:, 1] = ep/2-0.5, 0
points_d_test = np.concatenate((ep1, ep2, ep3, ep4, ep5)) # get the coordinate of the essential boundary points
points_d_test = np.unique(points_d_test, axis=0) # exclude the same points
kdt_t = KDTree(points_d_test, metric='euclidean') # for more accurate evaluation


# obtain 4 boundary points
ep = np.linspace(-1, 1, n_d) # distribute points from -1 to 1 uniformly
ep1 = np.zeros((n_d, 2)) # up
ep1[:, 0], ep1[:, 1] = ep, 1
ep2 = np.zeros((n_d, 2)) # down
ep2[:, 0], ep2[:, 1] = ep, -1
ep3 = np.zeros((n_d, 2)) # left
ep3[:, 0], ep3[:, 1] = -1, ep
ep4 = np.zeros((n_d, 2)) # right
ep4[:, 0], ep4[:, 1] = 1, ep
ep5 = np.zeros((n_d, 2)) # center
ep5[:, 0], ep5[:, 1] = ep, 0
ep5 = ep5[ep5[:,0]<=0]
points_d = np.concatenate((ep1, ep2, ep3, ep4, ep5)) # get the coordinate of the essential boundary points
points_d = np.unique(points_d, axis=0) # exclude the same points
kdt = KDTree(points_d, metric='euclidean') # make the essential boundary points to be a object.

domx = np.linspace(-1, 1, n_dom)[1:-1] # get the domain points
domy = np.linspace(-1, 1, n_dom)[1:-1] 
domx, domy = np.meshgrid(domx, domy)
domxy = np.stack((domx.flatten(), domy.flatten()), 1)
domxy = domxy[(domxy[:, 1]!=0)|(domxy[:, 0]>0)] 
d_dir, _ = kdt.query(points_d, k=1, return_distance = True) # get the distance label of the boundary points (0)
d_dom, _ = kdt.query(domxy, k=1, return_distance = True) # get the distance label of the dom points
# piece the essential and domain points
d_total = np.concatenate((points_d, domxy))

start = time.time()
# get the K matrix used to determine the weight of RBF
dx = d_total[:, 0][:, np.newaxis] - d_total[:, 0][np.newaxis, :]
dy = d_total[:, 1][:, np.newaxis] - d_total[:, 1][np.newaxis, :]
R = np.sqrt(dx**2+dy**2)
K = np.exp(-gama*R)

b = np.concatenate((d_dir, d_dom)) # the label of the distance corresponding to every points
w = np.dot(np.linalg.inv(K),b) # get the weight of the RBF
end = time.time()
consume_time_RBF = end-start

n_test = 201 # obtain the test points for the contourf plot, the number of the test points is n_test**2
domx_t = np.linspace(-1, 1, n_test)
domy_t = np.linspace(-1, 1, n_test)
domx_t, domy_t = np.meshgrid(domx_t, domy_t)
domxy_t = np.stack((domx_t.flatten(), domy_t.flatten()), 1)
domxy_t= torch.from_numpy(domxy_t).requires_grad_(True) # it is possible to AD with respect to the coordinates

dis_RBF = RBF(domxy_t) # get the distance result by RBF




# get average error of the RBF network
dis_RBF_test = RBF(torch.from_numpy(points_d_test)).numpy()
L2_rbf = np.sqrt(np.mean(dis_RBF_test**2))
print('L2 error of the RBF is '+str(L2_rbf))
MAE_rbf = np.mean(np.abs(dis_RBF_test))
print('MAE error of the RBF is '+str(MAE_rbf))
# =============================================================================
#  use neural network to approximate distance function
# =============================================================================
class NN(torch.nn.Module):
    def __init__(self, D_in, H, D_out):
        """
        

        Parameters
        ----------
        D_in : int
            the input dimension of the NN.
        H : int
            the number of the neurons in each hidden layer (the number of the layers is 3).
        D_out : int
            the output dimension, which is always same as the dimension of the D_in in PINN.

        Returns
        -------
        the distance function constructed by NN

        """
        super(NN, self).__init__()
        self.linear1 = torch.nn.Linear(D_in, H)
        self.linear2 = torch.nn.Linear(H, H)
        self.linear3 = torch.nn.Linear(H, H)
        self.linear4 = torch.nn.Linear(H, D_out)

        torch.nn.init.normal_(self.linear1.weight, mean=0, std=np.sqrt(2/(D_in+H)))
        torch.nn.init.normal_(self.linear2.weight, mean=0, std=np.sqrt(2/(H+H)))
        torch.nn.init.normal_(self.linear3.weight, mean=0, std=np.sqrt(2/(H+H)))
        torch.nn.init.normal_(self.linear4.weight, mean=0, std=np.sqrt(2/(H+D_out)))
        
        torch.nn.init.normal_(self.linear1.bias, mean=0, std=1)
        torch.nn.init.normal_(self.linear2.bias, mean=0, std=1)
        torch.nn.init.normal_(self.linear3.bias, mean=0, std=1)
        torch.nn.init.normal_(self.linear4.bias, mean=0, std=1)

    def forward(self, x):
        """
        In the forward function we accept a Tensor of input data and we must return
        a Tensor of output data. We can use Modules defined in the constructor as
        well as arbitrary operators on Tensors.
        """

        y1 = torch.tanh(self.linear1(x))
        y2 = torch.tanh(self.linear2(y1))
        y3 = torch.tanh(self.linear3(y2))
        y = self.linear4(y3)
        return y    

# learning the distance neural network
tol = 0.001

distance_nn = NN(2, 10, 1).cuda()
criterion = torch.nn.MSELoss()
optim = torch.optim.Adam(params=distance_nn.parameters(), lr= 0.001)
scheduler = torch.optim.lr_scheduler.MultiStepLR(optim, milestones=[1000, 3000, 5000], gamma = 0.1)
loss_array = []
MAE_NN_array = [100]
d_total_nn = torch.from_numpy(d_total).cuda()
label_nn = torch.from_numpy(b).cuda()
epoch = 0
start = time.time()
while MAE_NN_array[-1] > MAE_rbf:
    epoch = epoch + 1
    if epoch%10000 ==0: # test the average error on the essential boundary  every 10000 epochs.
        dis_NN_test = distance_nn(torch.from_numpy(points_d_test).cuda()).data.cpu().numpy()
        MAE_NN = np.mean(dis_NN_test)
        MAE_NN_array.append(MAE_NN)
        print('L2 error of the NN is '+str(MAE_NN))
    def closure():  
        pred_RBF_nn = distance_nn(d_total_nn) # predict the boundary condition
        loss = criterion(pred_RBF_nn, label_nn) 
        optim.zero_grad()
        loss.backward()
        loss_array.append(loss.data.cpu())
        if epoch%100==0:
            print(' epoch : %i, the loss : %f ' % (epoch, loss.data))
        return loss
    optim.step(closure)
    scheduler.step()
end = time.time()
consume_time_nn = end-start

# for plot the distance contourf by NN
n_test = 201 # obtain the test points for the contourf plot, the number of the test points is n_test**2
domx_t = np.linspace(-1, 1, n_test)
domy_t = np.linspace(-1, 1, n_test)
domx_t, domy_t = np.meshgrid(domx_t, domy_t)
domxy_t = np.stack((domx_t.flatten(), domy_t.flatten()), 1)
domxy_t= torch.from_numpy(domxy_t).cuda() # it is possible to AD with respect to the coordinates
dis_NN_test = distance_nn(domxy_t).data.cpu().numpy()
dis_NN_test = dis_NN_test.reshape(n_test, n_test)


#%%
#for paper plot
fig = plt.figure(dpi=1000,figsize = (13.5,3))
fig.tight_layout()
#plt.subplots_adjust(wspace = 0.4, hspace=0)

plt.subplot(1, 3, 1)
# plot the distribution points of RBF
plt.scatter(d_total[:, 0], d_total[:, 1])
ax = plt.gca()
ax.set_aspect(1)
plt.xlabel('x')
plt.ylabel('y')
plt.title('RBF points', size = 7)

plt.subplot(1, 3, 2)
# for plot the distance contourf by RBF
dis_plot_RBF = dis_RBF.data.cpu().numpy().reshape(n_test, n_test)
h1 = plt.contourf(domx_t, domy_t, dis_plot_RBF,  cmap = 'jet', levels = 100)
ax = plt.gca()
ax.set_aspect(1)
plt.colorbar(h1)
plt.xlabel('x')
plt.ylabel('y')
plt.title('RBF distance function', size = 7)

plt.subplot(1, 3, 3)
# for plot the distance contourf by NN
h1 = plt.contourf(domx_t, domy_t, dis_NN_test,  cmap = 'jet', levels = 100)
ax = plt.gca()
ax.set_aspect(1)
plt.colorbar(h1)
plt.xlabel('x')
plt.ylabel('y')
plt.title('NN distance function', size = 7)
plt.savefig('./distance_RBF_NN2.pdf', bbox_inches = 'tight')
plt.show()

print('RBF time is %f' % consume_time_RBF)
print('NN time is %f' % consume_time_nn)
print('NN/RBF time is %f' % (consume_time_nn/consume_time_RBF))

