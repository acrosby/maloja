from . import entities

catest = "Test Authority"
networkip = "10.100.100.0"
neworkcidr = 24


def test_NebulaNetwork_nonodes():
    testnet = entities.NebulaNetwork(
        cert_authority=catest,
        ip=networkip,
        cidr=networkcidr,
    )


def test_NebulaNode():
    n = entities.NebulaNode(name="autoiptest")


def test_Lighthouse():
    n = entities.NebulaNode(name="lhnode", am_lighthouse=True)


def test_NebulaNode_IP():
    n = entities.NebulaNode(name="specifiedip", ip="10.100.100.5")


def test_NebulaNetwork():
    nodes = [
        entities.NebulaNode(name="mynode1", ip="10.100.100.5"),
        entities.NebulaNode(name="mylighthouse", ip="10.100.100.6", am_lighthouse=True),
        entities.NebulaNode(name="myraondomnode"),
    ]
    testnet = entities.NebulaNetwork(
        cert_authority=catest,
        ip=networkip,
        cidr=networkcidr,
        nodes=nodes,
    )
    print(testnet)
    print(testnet.network)
    assert nodes[0].ip > nodes[1].ip
    assert not (nodes[0].ip < nodes[1].ip)
    print([n for n in sorted([_.ip for _ in nodes])])
    print(testnet.lighthouses)
