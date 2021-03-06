from __future__ import print_function
import torch
import torchvision
import torchvision.transforms as transforms
import os

def data_provider(dataset, root, batch_size, n_threads=4, download=False):

    if dataset == 'mnist':
        transform  = transforms.Compose([
            transforms.ToTensor(),
            transforms.Normalize((0.1307, ), (0.3081))
        ])

        trainset = torchvision.datasets.MNIST(
                    root=root,
                    train=True,
                    download=download,
                    transform=transform
                )

        testset = torchvision.datasets.MNIST(
                    root=root,
                    train=False,
                    download=download,
                    transform=transform
                )

    elif dataset == 'svhn':
        transform  = transforms.Compose([
            transforms.ToTensor(),
            transforms.Normalize((0.5, 0.5, 0.5), (0.5, 0.5, 0.5))
        ])

        trainset = torchvision.datasets.MNIST(
                    root=root,
                    train=True,
                    download=download,
                    transform=transform,
                    target_transform=lambda x: int(x[0]) - 1
                )

        testset = torchvision.datasets.MNIST(
                    root=root,
                    train=False,
                    download=download,
                    transform=transform,
                    target_transform=lambda x: int(x[0]) - 1
                )

    elif dataset == 'cifar10':
        norm_mean = [0.49139968, 0.48215827, 0.44653124]
        norm_std = [0.24703233, 0.24348505, 0.26158768]

        train_transform = transforms.Compose([
            transforms.RandomCrop(32, padding=4),
            transforms.RandomHorizontalFlip(),
            transforms.ToTensor(),
            transforms.Normalize(norm_mean, norm_std)])

        test_transform = transforms.Compose([
            transforms.ToTensor(),
            transforms.Normalize(norm_mean, norm_std)])


        trainset = torchvision.datasets.CIFAR10(
                    root=root,
                    train=True,
                    download=download,
                    transform=train_transform
                )

        testset = torchvision.datasets.CIFAR10(
                    root=root,
                    train=False,
                    download=download,
                    transform=test_transform
                )

    elif dataset == 'cifar100':
        norm_mean = [0.50705882, 0.48666667, 0.44078431]
        norm_std = [0.26745098, 0.25568627, 0.27607843]
        
        train_transform = transforms.Compose([
            transforms.RandomCrop(32, padding=4),
            transforms.RandomHorizontalFlip(),
            transforms.ToTensor(),
            transforms.Normalize(norm_mean, norm_std)])

        test_transform = transforms.Compose([
            transforms.ToTensor(),
            transforms.Normalize(norm_mean, norm_std)])


        trainset = torchvision.datasets.CIFAR100(
                    root=root,
                    train=True,
                    download=download,
                    transform=train_transform
                )

        testset = torchvision.datasets.CIFAR100(
                    root=root,
                    train=False,
                    download=download,
                    transform=test_transform
                )
    
    elif dataset == 'imagenet':
        normalize = transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])

        trainset = torchvision.datasets.ImageFolder(
                        os.path.join(root,"train"),
                        transforms.Compose([
                            transforms.RandomResizedCrop(224),
                            transforms.RandomHorizontalFlip(),
                            transforms.ToTensor(),
                            normalize,
                        ]))
        
        testset =  torchvision.datasets.ImageFolder(
                        os.path.join(root,"val"),
                        transforms.Compose([
                            transforms.RandomResizedCrop(224),
                            transforms.RandomHorizontalFlip(),
                            transforms.ToTensor(),
                            normalize,
                        ]))

    
    trainloader = torch.utils.data.DataLoader(
        trainset, batch_size=batch_size, shuffle=True, pin_memory=True, num_workers=n_threads)

    testloader = torch.utils.data.DataLoader(
        testset, batch_size=batch_size, shuffle=True, pin_memory=True, num_workers=n_threads)

    return trainloader, testloader

#test
# if __name__ == "__main__":
#     traindl, testdl = data_provider('cifar10', './', 32)
#     for idx,batch in enumerate(traindl):
#         img = batch[0]
#         label = batch[1]
#         print(idx, img.size(), label.size())
    