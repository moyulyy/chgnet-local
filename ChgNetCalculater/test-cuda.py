import torch
from chgnet.model import CHGNet

# Load pretrained CHGNet
model = CHGNet.load()

# Check if CUDA is available
if torch.cuda.is_available():  
    num_devices = torch.cuda.device_count()
    print(f'Number of CUDA devices: {num_devices}')
    
    for i in range(num_devices):
        device = torch.device(f'cuda:{i}')
        print(f'Device name: {torch.cuda.get_device_name(i)}')

        # Check whether we can move CHGNet to this device
        model.to(f'cuda:{i}')
        print(f"CHGNet is on device {i}")

        # Now your model is on the CUDA device with ID 'i'
else: 
    print('CUDA is not available.')
    
try:
    model.to('cuda')
except:
    raise Exception('can not move to cuda')