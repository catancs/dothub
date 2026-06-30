def test_password_hash_verify():
    from app.security import hash_password, verify_password
    h = hash_password("hunter2")
    assert verify_password("hunter2", h) is True
    assert verify_password("wrong", h) is False

def test_api_key_generation_and_hash():
    from app.security import generate_api_key, hash_api_key
    plain, key_hash = generate_api_key()
    assert plain.startswith("dh_")
    assert hash_api_key(plain) == key_hash
    assert hash_api_key("dh_other") != key_hash
