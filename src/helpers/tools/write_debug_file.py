import json

def write_debug_file(filename, data):
    with open(f"output/{filename}", "w") as f:
        json.dump(data, f, indent=2, default=str)
