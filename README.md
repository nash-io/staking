<p align="center">
  <img
    src="http://neonexchange.org/img/NEX-logo.svg"
    width="125px;">
    
</p>
<h3 align="center">NEX Staking Smart Contract</h3>
<hr/>



#### Installation

Clone the repository and navigate into the project directory. 
Make a Python 3 virtual environment and activate it via

```shell
python3 -m venv venv
source venv/bin/activate
```

or to explicitly install Python 3.6 via

    virtualenv -p /usr/local/bin/python3.6 venv
    source venv/bin/activate

Then install the requirements via

```shell
(venv) pip install -r requirements.txt
```

#### Compilation / Build

- Manual
    The template may be manually compiled from the Python shell as follows
    
    ```python
    from boa.compiler import Compiler
    
    Compiler.load_and_save('NexStaking.py')
    ```
    
    This will compile the contract to `NEX_Staking.avm`


#### Bug Reporting

Please contact us at bugbounty@neonexchange.org if you find something you believe we should know about.
