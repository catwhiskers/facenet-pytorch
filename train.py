# from facenet_pytorch import MTCNN, InceptionResnetV1, fixed_image_standardization, training
from models.inception_resnet_v1 import InceptionResnetV1
from models.mtcnn import MTCNN, fixed_image_standardization
from models.utils import training

import torch
from torch.utils.data import DataLoader, SubsetRandomSampler
from torch import optim
from torch.optim.lr_scheduler import MultiStepLR
from torch.utils.tensorboard import SummaryWriter
from torchvision import datasets, transforms
import numpy as np
import os
import json 

data_dir = '/opt/ml/input/data/faces'
model_dir = '/opt/ml/model'
hyperparameter_f = '/opt/ml/input/config/hyperparameters.json'



hyperparameters = {'batch_size':'32', 
                   'epochs':'8', 
                   'workers':'0',
                  'learning_rate':'0.001', 
                  }

if os.path.exists(hyperparameter_f):
    chypers = json.load(open(hyperparameter_f, 'r'))
    hyperparameters.update(chypers)
    




device = torch.device('cuda:0' if torch.cuda.is_available() else 'cpu')
print('Running on device: {}'.format(device))


mtcnn = MTCNN(
    image_size=160, margin=0, min_face_size=20,
    thresholds=[0.6, 0.7, 0.7], factor=0.709, post_process=True,
    device=device
)


dataset = datasets.ImageFolder(data_dir, transform=transforms.Resize((512, 512)))
dataset.samples = [
    (p, p.replace(data_dir, data_dir + '_cropped/'))
        for p, _ in dataset.samples
]
        
loader = DataLoader(
    dataset,
    num_workers=int(hyperparameters['workers']),
    batch_size=int(hyperparameters['batch_size']),
    collate_fn=training.collate_pil
)

for i, (x, y) in enumerate(loader):
    mtcnn(x, save_path=y)
    print('\rBatch {} of {}'.format(i + 1, len(loader)), end='')
    
# Remove mtcnn to reduce GPU memory usage
del mtcnn


resnet = InceptionResnetV1(
    classify=True,
    pretrained='vggface2',
    num_classes=len(dataset.class_to_idx)
).to(device)


optimizer = optim.Adam(resnet.parameters(), lr=float(hyperparameters['learning_rate']))
scheduler = MultiStepLR(optimizer, [5, 10])

trans = transforms.Compose([
    np.float32,
    transforms.ToTensor(),
    fixed_image_standardization
])
dataset = datasets.ImageFolder(data_dir + '_cropped', transform=trans)
img_inds = np.arange(len(dataset))
np.random.shuffle(img_inds)
train_inds = img_inds[:int(0.8 * len(img_inds))]
val_inds = img_inds[int(0.8 * len(img_inds)):]

train_loader = DataLoader(
    dataset,
    num_workers=int(hyperparameters['workers']),
    batch_size=int(hyperparameters['batch_size']),
    sampler=SubsetRandomSampler(train_inds)
)
val_loader = DataLoader(
    dataset,
    num_workers=int(hyperparameters['workers']),
    batch_size=int(hyperparameters['batch_size']),
    sampler=SubsetRandomSampler(val_inds)
)

loss_fn = torch.nn.CrossEntropyLoss()
metrics = {
    'fps': training.BatchTimer(),
    'acc': training.accuracy
}


epochs = int(hyperparameters['epochs'])


writer = SummaryWriter()
writer.iteration, writer.interval = 0, 10

print('\n\nInitial')
print('-' * 10)
resnet.eval()
training.pass_epoch(
    resnet, loss_fn, val_loader,
    batch_metrics=metrics, show_running=True, device=device,
    writer=writer
)


for epoch in range(epochs):
    print('\nEpoch {}/{}'.format(epoch + 1, epochs))
    print('-' * 10)

    resnet.train()
    training.pass_epoch(
        resnet, loss_fn, train_loader, optimizer, scheduler,
        batch_metrics=metrics, show_running=True, device=device,
        writer=writer
    )

    resnet.eval()
    training.pass_epoch(
        resnet, loss_fn, val_loader,
        batch_metrics=metrics, show_running=True, device=device,
        writer=writer
    )

writer.close()

torch.save(resnet, os.path.join(model_dir, "fine_tuned_model"))
