from six.moves import urllib
opener = urllib.request.build_opener()
opener.addheaders = [('User-agent', 'Mozilla/5.0')]
urllib.request.install_opener(opener)

import torch
import numpy as np
import torchvision
import matplotlib
import matplotlib.pyplot as plt
import torch.nn as nn
import torch.nn.functional as F
from torchvision.datasets import CIFAR10
from torchvision import transforms
from torchvision.transforms import ToTensor
from torch.utils.data.dataloader import DataLoader
from torch.utils.data import random_split
from torch.utils.data import Dataset
from torch.nn.modules.loss import TripletMarginLoss
from itertools import permutations, product
from datetime import datetime
import time
from sklearn.neighbors import KNeighborsClassifier
from sklearn import metrics
from pytorch_metric_learning import losses, reducers
import argparse

parser = argparse.ArgumentParser(description='Margin Loss - Cifar10 dataset')
parser.add_argument('-bs','--batch_size', type=int, metavar='', required=True, help='Batch size')
parser.add_argument('-eps','--epochs', type=int, metavar='', required=True, help='Number of epochs')
parser.add_argument('-lr','--learn_rate', type=float, metavar='', required=True, help='Learning rate')
parser.add_argument('-m','--margin', type=float, metavar='', required=True, help='Margin of the equation')
parser.add_argument('-bt','--beta', type=float, metavar='', required=True, help='Beta of the equation')

args = parser.parse_args()

#####################################################################################################################

def Metrics(y_real, y_pred):
    acc = metrics.accuracy_score(y_real, y_pred)
    prec = metrics.precision_score(y_real, y_pred, average='macro')
    rec = metrics.recall_score(y_real, y_pred, average='macro')
    f = metrics.f1_score(y_real, y_pred, average='macro')

    print("The average scores for all classes:")
    # Calculate metrics for each label, and find their unweighted mean. does not take label imbalance into account.
    print("\nAccuracy:  {:.2f}%".format(acc * 100))  # (TP+TN)/Total / number of classes
    print("Precision: {:.2f}%".format(prec * 100))  # TP/(TP+FP) / number of classes
    print("Recall:    {:.2f}%".format(rec * 100))  # TP/(TP+FN) / number of classes
    print("F-measure: {:.2f}%".format(f * 100))  # 2 * (prec*rec)/(prec+rec) / number of classes

    print("\nThe scores for each class:")
    precision, recall, fscore, support = metrics.precision_recall_fscore_support(y_real, y_pred)

    print("\n|    Label    |  Precision |  Recall  | F1-Score | Support")
    print("|-------------|------------|----------|----------|---------")
    for i in range(num_classes):
        print(
            f"| {classes[i]:<11} |  {precision[i] * 100:<7.2f}%  | {recall[i] * 100:<7.2f}% |   {fscore[i]:<4.2f}   | {support[i]}")

    return acc

color = ['tab:blue', 'tab:orange', 'tab:green', 'tab:red', 'tab:purple', 'tab:brown', 'tab:pink', 'tab:gray', 'tab:olive', 'tab:cyan']
marker = ['.','+','x','1','^','s','p','*','d','X']
classes = ['Plane', 'Car', 'Bird', 'Cat', 'Deer', 'Dog', 'Frog', 'Horse', 'Ship', 'Truck']

def Ploting2D(embeddings_plot,labels_plot,tit="default",x_axis="X",y_axis="Y"):
    ax = plt.figure().add_subplot(111)
    for i in range(num_classes):
        index = labels_plot == i
        plt.scatter(embeddings_plot[0, index], embeddings_plot[1, index], s=3, marker='.', c=color[i], label=classes[i])
    ax.legend(loc='best', title="Labels", markerscale=5.0)

    # add grid
    plt.grid(True,linestyle='--')

    # add title
    plt.title(tit)
    plt.tight_layout()

    # add x,y axes labels
    plt.xlabel(x_axis)
    plt.ylabel(y_axis)

def Ploting3D(embeddings_plot, labels_plot, tit="default",x_axis="X",y_axis="Y",z_axis="Z"):
    ax = plt.figure().gca(projection='3d')
    for i in range(num_classes):
        index = labels_plot == i
        ax.scatter(embeddings_plot[0, index], embeddings_plot[1, index], embeddings_plot[2, index], s=3, marker='.',c=color[i], label=classes[i])
    ax.legend(loc='best', title="Labels", markerscale=5.0)

    # add title
    plt.title(tit)
    plt.tight_layout()

    # add x,y axes labels
    ax.set_xlabel(x_axis)
    ax.set_ylabel(y_axis)
    ax.set_zlabel(z_axis)

#####################################################################################################################
print("\nLOAD DATA\n")

mean, std = (0.49139968, 0.48215827, 0.44653124), (0.24703233, 0.24348505, 0.26158768) #CIFAR

preprocess = transforms.Compose([
    transforms.ToTensor(),
    transforms.Normalize(mean, std) ])

#Load Data
train_dataset = CIFAR10(root='dataset/', train=True, transform=preprocess, download='True')
test_dataset = CIFAR10(root='dataset/', train=False, transform=preprocess, download='True')

# Create validation & training datasets
val_size = int(len(train_dataset) * 0.20)
train_size = len(train_dataset) - val_size
train_ds, val_ds = random_split(train_dataset, [train_size, val_size])

#Dataset to Batches
batch_size = args.batch_size #128 <-----------------------------------------------------------------------------------------
train_ld = DataLoader(train_ds, batch_size=batch_size, shuffle=True)
val_ld = DataLoader(val_ds, batch_size=batch_size, shuffle=False)

##################################################### Using a GPU #####################################################
cuda = torch.cuda.is_available()
device = torch.device('cuda' if cuda else 'cpu')

print("\nUSING", device)
if cuda:
    num_dev = torch.cuda.current_device()
    print(torch.cuda.get_device_name(num_dev),"\n")

def to_device(data, device):
    """Move tensor(s) to chosen device"""
    if isinstance(data, (list,tuple)):
        return [to_device(x, device) for x in data]

    return data.to(device, non_blocking=True)

class DeviceDataLoader():
    """Wrap a dataloader to move data to a device"""
    def __init__(self, data, device):
        self.data = data
        self.device = device

    def __iter__(self):
        """Yield a batch of data after moving it to device"""
        for data in self.data:
            yield to_device(data, self.device)

    def __len__(self):
        """Number of batches"""
        return len(self.data)

#Batches to GPU
train_ld = DeviceDataLoader(train_ld, device)
val_ld = DeviceDataLoader(val_ld, device)

#####################################################################################################################
print("\nNETWORK TRAINING\n")

class BasicBlock(nn.Module):
    expansion = 1

    def __init__(self, in_planes, planes, stride=1):
        super(BasicBlock, self).__init__()
        self.conv1 = nn.Conv2d(in_planes, planes, kernel_size=3, stride=stride, padding=1, bias=False)
        self.bn1 = nn.BatchNorm2d(planes)
        self.conv2 = nn.Conv2d(planes, planes, kernel_size=3, stride=1, padding=1, bias=False)
        self.bn2 = nn.BatchNorm2d(planes)

        self.shortcut = nn.Sequential()
        if stride != 1 or in_planes != self.expansion*planes:
            self.shortcut = nn.Sequential(
                nn.Conv2d(in_planes, self.expansion*planes, kernel_size=1, stride=stride, bias=False),
                nn.BatchNorm2d(self.expansion*planes)
            )

    def forward(self, x):
        out = F.relu(self.bn1(self.conv1(x)))
        out = self.bn2(self.conv2(out))
        out += self.shortcut(x)
        out = F.relu(out)
        return out

class Bottleneck(nn.Module):
    expansion = 4

    def __init__(self, in_planes, planes, stride=1):
        super(Bottleneck, self).__init__()
        self.conv1 = nn.Conv2d(in_planes, planes, kernel_size=1, bias=False)
        self.bn1 = nn.BatchNorm2d(planes)
        self.conv2 = nn.Conv2d(planes, planes, kernel_size=3, stride=stride, padding=1, bias=False)
        self.bn2 = nn.BatchNorm2d(planes)
        self.conv3 = nn.Conv2d(planes, self.expansion * planes, kernel_size=1, bias=False)
        self.bn3 = nn.BatchNorm2d(self.expansion*planes)

        self.shortcut = nn.Sequential()
        if stride != 1 or in_planes != self.expansion*planes:
            self.shortcut = nn.Sequential(
                nn.Conv2d(in_planes, self.expansion*planes, kernel_size=1, stride=stride, bias=False),
                nn.BatchNorm2d(self.expansion*planes)
            )

    def forward(self, x):
        out = F.relu(self.bn1(self.conv1(x)))
        out = F.relu(self.bn2(self.conv2(out)))
        out = self.bn3(self.conv3(out))
        out += self.shortcut(x)
        out = F.relu(out)
        return out

class Triplet_Network(nn.Module):
    def __init__(self, block, num_blocks, in_channels=3, output_size=2, m=1.0, beta=1.2):
        super(Triplet_Network, self).__init__()
        self.in_planes = 64

        self.conv1 = nn.Conv2d(in_channels, 64, kernel_size=3, stride=1, padding=1, bias=False)
        self.bn1 = nn.BatchNorm2d(64)
        self.layer1 = self._make_layer(block, 64, num_blocks[0], stride=1)
        self.layer2 = self._make_layer(block, 128, num_blocks[1], stride=2)
        self.layer3 = self._make_layer(block, 256, num_blocks[2], stride=2)
        self.layer4 = self._make_layer(block, 512, num_blocks[3], stride=2)
        self.linear = nn.Linear(512*block.expansion, output_size)

        self.margin_loss = losses.MarginLoss(margin=m, nu=0, beta=beta, triplets_per_anchor="all", learn_beta=False, num_classes=10, reducer=reducers.MeanReducer())
        self.margin_loss_without_reduction = losses.MarginLoss(margin=m, nu=0, beta=beta, triplets_per_anchor="all", learn_beta=False,
                                             num_classes=10, reducer=reducers.DoNothingReducer())

    def _make_layer(self, block, planes, num_blocks, stride):
        strides = [stride] + [1]*(num_blocks-1)
        layers = []
        for stride in strides:
            layers.append(block(self.in_planes, planes, stride))
            self.in_planes = planes * block.expansion
        return nn.Sequential(*layers)

    def forward(self, x):
        out = F.relu(self.bn1(self.conv1(x)))
        out = self.layer1(out)
        out = self.layer2(out)
        out = self.layer3(out)
        out = self.layer4(out)
        out = F.avg_pool2d(out, 4)
        out = out.view(out.size(0), -1)
        out = self.linear(out)
        return out

    def training_step(self, batch):
        data, labels = batch

        # Generate predictions
        embeddings = self(data)

        # Calculate loss
        loss = self.margin_loss(embeddings, labels)

        return loss

    def extract_embedding(self, dataset):
        size_batch = len(dataset)//20 #change this if not enough memory

        data_loader = DataLoader(dataset=dataset, batch_size=size_batch, shuffle=False)
        data_loader = DeviceDataLoader(data_loader, 'cuda')

        with torch.no_grad():
            self.train()
            embedding = torch.tensor([]).to('cuda')
            for batch in data_loader:
                data, _ = batch
                embedded = self.forward(data)
                embedding = torch.cat((embedding, embedded), 0)

        embedding = embedding.cpu().numpy()
        label = torch.tensor(dataset.targets).cpu().numpy()

        del data_loader, embedded, data
        torch.cuda.empty_cache()

        return embedding, label

    def evaluate_step(self, val_loader):
        with torch.no_grad():
            self.eval()

            val_loss = []
            #val_acc = []
            for batch in val_loader:
                data, labels = batch

                # Generate predictions
                embeddings = self(data)

                losses = self.margin_loss_without_reduction(embeddings, labels)["margin_loss"]["losses"]

                # Calculate loss
                loss = torch.mean(losses)

                # Calculate accuracy
                #acc = (losses <= 0).sum() * 1.0 / len(losses)

                val_loss.append(loss.item())
                #val_acc.append(acc.item())

        epoch_loss = torch.tensor(val_loss).mean()  # Combine losses
        #epoch_acc = torch.tensor(val_acc).mean()  # Combine accuracies

        #return {'val_loss': epoch_loss.item(), 'val_acc': epoch_acc.item()}
        return {'val_loss': epoch_loss.item()}

def ResNet_size(size=10, in_channels=3, output_size=2, margin = 1.0, beta=1.2):
    if size == 10:
        return Triplet_Network(BasicBlock, [1, 1, 1, 1], in_channels=in_channels, output_size=output_size, m=margin, beta=beta)
    elif size == 18:
        return Triplet_Network(BasicBlock, [2, 2, 2, 2], in_channels=in_channels, output_size=output_size, m=margin, beta=beta)
    elif size == 34:
        return Triplet_Network(BasicBlock, [3, 4, 6, 3], in_channels=in_channels, output_size=output_size, m=margin, beta=beta)
    elif size == 50:
        return Triplet_Network(Bottleneck, [3, 4, 6, 3], in_channels=in_channels, output_size=output_size, m=margin, beta=beta)
    elif size == 101:
        return Triplet_Network(Bottleneck, [3, 4, 23, 3], in_channels=in_channels, output_size=output_size, m=margin, beta=beta)
    elif size == 152:
        return Triplet_Network(Bottleneck, [3, 8, 36, 3], in_channels=in_channels, output_size=output_size, m=margin, beta=beta)

def get_lr(optimizer):
    for param_group in optimizer.param_groups:
        return param_group['lr']

def fit(epochs, max_lr, model, train_loader, val_loader, weight_decay=0.0, grad_clip=None, opt_func=torch.optim.SGD):
    torch.cuda.empty_cache()
    # history = []

    # Set up cutom optimizer with weight decay
    optimizer = opt_func(model.parameters(), max_lr, weight_decay=weight_decay)
    # Set up learning rate scheduler
    sched = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, factor=0.80, patience=2, verbose=True)

    for epoch in range(epochs):
        model.train()  # tells the model is in training mode, so batchnorm, dropout and all the ohter layer that have a training mode should get to the training mode

        train_losses = []
        lrs = []

        # Training Phase
        for batch in train_loader:

            optimizer.zero_grad()  # Reset the gradients

            loss = model.training_step(batch)  # Generate predictions, calculate loss
            train_losses.append(loss.item())

            loss.backward()  # Compute gradients

            # Gradient clipping
            if grad_clip:
                nn.utils.clip_grad_value_(model.parameters(), grad_clip)

            optimizer.step()  # Adjust the weights

        # Record & update learning rate
        mean_loss = torch.tensor(train_losses).mean().item()
        lrs.append(get_lr(optimizer))
        sched.step(mean_loss)

        # Validation phase
        result = model.evaluate_step(val_loader)
        result['train_loss'] = mean_loss
        result['lrs'] = lrs

        #print(f"Epoch [{epoch + 1}/{epochs}], last_lr: {lrs[-1]:.5f}, train_loss: {mean_loss:.4f}, val_loss: {result['val_loss']:.4f}, val_acc: {result['val_acc']:.4f}")

        print(f"Epoch [{epoch + 1}/{epochs}], last_lr: {lrs[-1]:.5f}, train_loss: {mean_loss:.4f}, val_loss: {result['val_loss']:.4f}")


# Parameters
num_classes = 10
output_dim = 2
epochs = args.epochs     #30 <-----------------------------------------------------------------------------------------
max_lr = args.learn_rate   #0.1 <-----------------------------------------------------------------------------------------
margin = args.margin    #0.5 <-----------------------------------------------------------------------------------------
beta = args.beta         #0.8 <-----------------------------------------------------------------------------------------

grad_clip = 0.1 # if ||g|| > u, g <- gu/||g||
weight_decay = 1e-4
opt_func = torch.optim.SGD #RMSprop SGD Adam

print(f"Output dimension: {output_dim}\n")

# Model (on Device)
Network_model = to_device(ResNet_size(size=18, in_channels=3, output_size=output_dim, margin=margin, beta=beta), device)

# Train ResNet
print(f"[{datetime.now()}]")
start = time.time()

fit(epochs=epochs, max_lr=max_lr, model=Network_model, train_loader=train_ld, val_loader=val_ld, weight_decay=weight_decay, grad_clip=grad_clip, opt_func=opt_func)

end = time.time()-start
print(f"[{datetime.now()}]")
print(f"\nTotal time = {int(end//3600):02d}:{int((end//60))%60:02d}:{end%60:.6f}")

#####################################################################################################################
del train_ld, val_ld
torch.cuda.empty_cache() # PyTorch thing
#####################################################################################################################
print("\nPLOTTING NEW SPACE\n")

embeddings_plot, labels_plot = Network_model.extract_embedding(train_dataset)

''' uncomment if you want to plot the resulting embeddings
if output_dim == 2:
    Ploting2D(embeddings_plot.T, labels_plot, "Learned Data Space")
if output_dim == 3:
    Ploting3D(embeddings_plot.T, labels_plot, "Learned Data Space")
'''
########################################### Evaluation ##############################################################
knn = KNeighborsClassifier(n_neighbors=1) #algorithm auto = ball_tree, kd_tree or brute
knn.fit(embeddings_plot, labels_plot)
#####################################################################################################################
print("\nPLOTTING GENERALIZATION\n")

embeddings_plot, labels_plot = Network_model.extract_embedding(test_dataset)

''' uncomment if you want to plot the resulting embeddings
if output_dim == 2:
    Ploting2D(embeddings_plot.T, labels_plot, "Learned Data Embedding")
if output_dim == 3:
    Ploting3D(embeddings_plot.T, labels_plot, "Learned Data Embedding")
'''
########################################### Evaluation ##############################################################
y_pred = knn.predict(embeddings_plot)

acc = Metrics(labels_plot, y_pred)

#####################################################################################################################
print("\nSAVING NETWORK MODEL\n")
#The .state_dict method returns an OrderedDict containing all the weights and bias matrices mapped to the right attributes of the model

File_name = "Log/Margin/Cifar10/" + str(output_dim) + "d/Cifar10_acc-" + str(acc) + "_bs-" + str(batch_size) + "_eps-" + str(epochs) + "_lr-" + str(max_lr) + "_m-" + str(margin) + "_b-" + str(beta) + ".pth"
torch.save(Network_model.state_dict(), File_name)
#####################################################################################################################

''' uncomment if you want to plot the resulting embeddings
if output_dim <= 3:
    plt.show()
'''