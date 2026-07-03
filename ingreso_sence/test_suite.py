#!/usr/bin/env python3
import os
import json
import unittest

class TestSuiteSence(unittest.TestCase):
    def setUp(self):
        self.config_path = "config_sence.json"
        self.backup_config = None
        if os.path.exists(self.config_path):
            with open(self.config_path, "r", encoding="utf-8") as f:
                self.backup_config = f.read()

        self.test_config = {
            "MODO_RAI": True,
            "directorios": {
                "entrada": "./test_entrada",
                "salida": "./test_salida"
            },
            "parametros_fijos": {
                "codigo_sence": "99999999",
                "rut_empresa": "11111111-1",
                "nombre_curso": "Curso Test Automatizado"
            }
        }
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(self.test_config, f, indent=4)

        os.makedirs("./test_entrada", exist_ok=True)
        os.makedirs("./test_salida", exist_ok=True)
        
        with open("./test_entrada/dummy_contrato.pdf", "w") as f:
            f.write("%PDF-1.4 dummy data")

    def tearDown(self):
        for f in ["./test_entrada/dummy_contrato.pdf", "./test_salida/01_Declaracion_Jurada.pdf", "./test_salida/02_Carta_Conductora.pdf", "./test_salida/03_Contratos.pdf"]:
            if os.path.exists(f):
                os.remove(f)
        for d in ["./test_entrada", "./test_salida"]:
            if os.path.exists(d):
                os.rmdir(d)
                
        if self.backup_config:
            with open(self.config_path, "w", encoding="utf-8") as f:
                f.write(self.backup_config)
        elif os.path.exists(self.config_path):
            os.remove(self.config_path)

    def test_pipeline_completo(self):
        import ingreso_sence
        ingreso_sence.main()
        
        self.assertTrue(os.path.exists("./test_salida/01_Declaracion_Jurada.pdf"), "❌ Faltó generar DJ")
        self.assertTrue(os.path.exists("./test_salida/02_Carta_Conductora.pdf"), "❌ Faltó generar Carta")
        self.assertTrue(os.path.exists("./test_salida/03_Contratos.pdf"), "❌ Faltó generar Contratos consolidado")
        print("\n✅ Pruebas automáticas integradas pasaron con éxito.")

if __name__ == "__main__":
    unittest.main()
