import json, sys, io

with open(r"f:\Trae code\002\backend\test\test_output.json", "rb") as fb:
    raw = fb.read()

# Auto-detect encoding
if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
    text = raw.decode("utf-16")
elif raw[:3] == b"\xef\xbb\xbf":
    text = raw[3:].decode("utf-8")
else:
    text = raw.decode("utf-8")

d = json.loads(text)
n = d["xlsx"]["nodes"][0]

print("=== First node ===")
for k, v in n.items():
    print(f"  {k}: {v}")

print(f"\nnodeCount={d['xlsx']['nodeCount']}")
print(f"actual nodes={len(d['xlsx']['nodes'])}")

bases = [x["node_0base"] for x in d["xlsx"]["nodes"]]
print(f"node_0base range: {min(bases)} - {max(bases)}")

has_wgs84 = sum(1 for x in d["xlsx"]["nodes"] if "wgs84_lng" in x)
print(f"nodes with wgs84_lng: {has_wgs84}")
