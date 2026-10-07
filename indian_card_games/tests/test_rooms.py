from multiplayer.room import RoomManager

def test_room_creation():
    rm=RoomManager(); r=rm.create('78','p1','A','s1')
    assert len(r.code)==5; assert r.capacity==2

def test_full_room():
    rm=RoomManager(); r=rm.create('78','p1','A','s1'); r.add_player('p2','B','s2')
    try: r.add_player('p3','C','s3'); assert False
    except ValueError: assert True
