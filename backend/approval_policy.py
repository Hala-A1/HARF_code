"""Channel routing defaults; each submission retains its own route snapshot."""
def final_layer(value):
    layer = value.get('final_approval_layer', 3)
    return layer if type(layer) is int and 1 <= layer <= 3 else 3
