nohup python3 -u main.py invoice >> invoice.log 2>&1 &
nohup python3 -u main.py payment >> payment.log 2>&1 &
nohup python3 -u main.py PayWithPurchase >> PayWithPurchase.log 2>&1 &
nohup python3 -u main.py PayWithRebate >> PayWithRebate.log 2>&1 &
nohup python3 -u main.py purchaseorder >> purchaseorder.log 2>&1 &
#nohup python3 -u main.py iepurchaseorder >> log 2>&1 &
######################################################################
nohup python3 -u main.py customer >> customer.log 2>&1 &
nohup python3 -u main.py account >> account.log 2>&1 &
nohup python3 -u main.py receivable >> receivable.log 2>&1 &
nohup python3 -u main.py productouts >> productouts.log 2>&1 &
nohup python3 -u main.py contract >> contract.log 2>&1 &
nohup python3 -u main.py cuscredit >> cuscredit.log 2>&1 &
nohup python3 -u main.py cuscomment >> cuscomment.log 2>&1 &

