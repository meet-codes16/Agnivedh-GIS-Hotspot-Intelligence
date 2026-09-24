from app.osm_facility import _named_facility_query, _parse_context_payload

LAT, LON = 21.10483, 72.6479
q = _named_facility_query(LAT, LON, 3000)
for needle in [
    '["landuse"="industrial"]',
    '["industrial"]',
    '["power"~"plant|generator|substation",i]',
    '["landuse"="military"]',
    '["military"]',
    '["plant:source"~"nuclear",i]',
]:
    assert needle in q, needle

payload = {"elements": [
    {"type":"way","id":1,"center":{"lat":LAT,"lon":LON},"tags":{"landuse":"industrial"}},
    {"type":"node","id":2,"lat":LAT+0.001,"lon":LON+0.001,"tags":{"military":"base","name":"Test Military Base"}},
    {"type":"node","id":3,"lat":LAT+0.002,"lon":LON+0.002,"tags":{"power":"substation"}},
    {"type":"node","id":4,"lat":LAT+0.003,"lon":LON+0.003,"tags":{"plant:source":"nuclear","name":"Test Nuclear Plant"}},
    {"type":"node","id":5,"lat":LAT+0.004,"lon":LON+0.004,"tags":{"man_made":"factory","name":"Test Factory"}},
]}
r = _parse_context_payload(payload, LAT, LON)
assert r['nearest_industry']['category'] == 'Industrial Facility'
assert r['nearest_industry']['display_name'] == 'Industrial Facility'
assert any(x['category'] == 'Military Installation' for x in r['nearby'])
assert any(x['category'] == 'Critical Power Infrastructure' for x in r['nearby'])
assert any(x['category'] == 'Nuclear Facility' for x in r['nearby'])
assert any(x['name'] == 'Test Factory' for x in r['nearby'])
print('OSM broad-context contract: PASS')
