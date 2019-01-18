<p align="center">
  <img
    src="http://neonexchange.org/img/NEX-logo.svg"
    width="125px;">

</p>
<h3 align="center">NEX Staking Smart Contract</h3>
<hr/>



## Installation

### System Requirements

You need Python 3 (3.7 or 3.6).

OSX

    brew install python

Debian/Ubuntu 16.10+

    sudo apt-get install python3.7 python3.7-dev python3.7-venv python3-pip

### Project Setup

Clone the repository and navigate into the project directory.
Make a Python 3 virtual environment and activate it via

```shell
python3 -m venv venv
source venv/bin/activate
```

Then install the requirements via

```shell
(venv) pip install -r requirements.txt
```

## Compilation / Build

The smart contract can be compiled from the Python shell as follows:

```python
from boa.compiler import Compiler

Compiler.load_and_save('NexStaking.py')
```

This will compile the contract to `NEX_Staking.avm`


## Bug Reporting

Please contact us at bugbounty@neonexchange.org if you find something you believe we should know about.
