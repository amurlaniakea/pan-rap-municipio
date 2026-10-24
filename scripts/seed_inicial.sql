-- 3 usuarios con códigos postales DIFERENTES (regla del aval cruzado)
INSERT INTO usuarios (id, codigo_postal, email, public_key, fecha_registro) VALUES
  (1, '28001', 'vecino_28001@local', '3056301006072a8648ce3d020106052b8104000a03420004237ce778340aa808fb17943ec57cd181513591e234743245d89ca86745ffc0f66d3f2bec33014d86b6e99ae4efa3fe2285cc693a3eeeb8dd8c782436217252cb', CURRENT_TIMESTAMP),
  (2, '28002', 'vecino_28002@local', '0288f3a1b2c3d4e5f67890123456789012345678901234567890123456789012345678901234567890abcd', CURRENT_TIMESTAMP),
  (3, '28003', 'profesor_28003@local', '03bb2a4c8d1e2f3a4b5c67890123456789012345678901234567890123456789012345678901234567890abcd', CURRENT_TIMESTAMP);

-- Propuesta piloto #1 (creador = usuario 1, CP 28001)
INSERT INTO propuestas (id, titulo, estado, fecha_creacion) VALUES
  (1, 'Renovación y equipamiento de la Plaza Central', 'en_debate', CURRENT_TIMESTAMP);

-- 5 comentarios de debate; comentario 5 = AVAL cruzado (usuario 2, CP 28002 ≠ 28001)
INSERT INTO comentarios (id, propuesta_id, usuario_id, cuerpo, fecha) VALUES
  (1, 1, 1, 'Es urgente renovar los bancos deteriorados del lado norte.', CURRENT_TIMESTAMP),
  (2, 1, 3, 'Como vecino del 28003, veo que la zona de juegos está inutilizable.', CURRENT_TIMESTAMP),
  (3, 1, 2, 'Apoyo con una observación: que el pavimento sea drenante.', CURRENT_TIMESTAMP),
  (4, 1, 1, 'Confirmo los datos del Informe Municipal 2025.', CURRENT_TIMESTAMP),
  (5, 1, 2, 'AVAL (cruzado CP 28002): respaldo la propuesta del vecino del 28001. Proyecto necesario para todo el municipio.', CURRENT_TIMESTAMP);

-- Propuesta extra para testing de voto (en_votacion)
INSERT INTO propuestas (id, titulo, estado, fecha_creacion) VALUES (2, 'Instalación de paneles solares en el polideportivo', 'en_votacion', CURRENT_TIMESTAMP);
