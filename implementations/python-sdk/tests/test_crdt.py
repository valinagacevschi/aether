from aether.crdt import GCounter, LWWRegister, ORSet, PNCounter


def test_gcounter_add_update_value() -> None:
    left = GCounter()
    right = GCounter()
    left.add(2, "a")
    right.add(5, "a")
    right.add(1, "b")
    left.update(right)
    assert left.value == 6


def test_pncounter_add_remove_value() -> None:
    counter = PNCounter()
    counter.add(4, "a")
    counter.remove(1, "a")
    counter.remove(2, "b")
    assert counter.value == 1


def test_lwwregister_update_remove() -> None:
    reg = LWWRegister[str]()
    reg.update("a", 1, "a")
    reg.update("b", 1, "b")
    assert reg.value == "b"
    reg.remove(2, "a")
    assert reg.value is None
    assert reg.tombstone is True


def test_orset_add_remove_elements() -> None:
    oset = ORSet[str]()
    oset.add("x", "t1")
    oset.add("x", "t2")
    oset.add("y", "t3")
    oset.remove("x", ["t1"])
    assert oset.elements() == {"x", "y"}
    oset.remove("x", ["t2"])
    assert oset.elements() == {"y"}
