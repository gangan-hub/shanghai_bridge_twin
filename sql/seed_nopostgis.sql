INSERT INTO users (username, password_hash, role)
VALUES
  ('admin', 'admin123', 'admin'),
  ('visitor', 'visitor123', 'visitor')
ON CONFLICT (username) DO NOTHING;

INSERT INTO bridges (
  code, name, district, bridge_type, span_m, built_year, design_unit, description, model_path, lon, lat
)
VALUES
  ('SH-BR-001', '南浦大桥', '黄浦区', '斜拉桥', 846.00, 1991, '上海市政设计院', '示例桥梁数据', '/models/SH-BR-001/tileset.json', 121.499, 31.210),
  ('SH-BR-002', '杨浦大桥', '杨浦区', '斜拉桥', 602.00, 1993, '上海市政设计院', '示例桥梁数据', '/models/SH-BR-002/tileset.json', 121.548, 31.259),
  ('SH-BR-003', '卢浦大桥', '黄浦区', '拱桥', 550.00, 2003, '上海现代设计集团', '示例桥梁数据', '/models/SH-BR-003/tileset.json', 121.472, 31.198)
ON CONFLICT (code) DO NOTHING;

