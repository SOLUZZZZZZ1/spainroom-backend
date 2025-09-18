# === Conocimiento ============================================================
KNOWLEDGE: Dict[str, Dict[str, Any]] = {
    "que_hace": {
        "patterns": ["que hac", "qué hac", "quienes sois", "qué es spainroom", "que es spainroom"],
        "answers": [
            "SpainRoom alquila habitaciones de medio y largo plazo. No somos hotel.",
            "Intermediamos, validamos documentación y firmamos digitalmente para su seguridad.",
        ],
    },
    "minimo_precios": {
        "patterns": ["minimo", "mínimo", "precio", "precios", "tarifa"],
        "answers": [
            "La estancia mínima es de un mes. El precio depende de la habitación y la zona.",
            "Le ayudamos a comparar opciones disponibles en su ciudad.",
        ],
    },
    "documentos": {
        "patterns": ["document", "dni", "pasaporte", "requisitos"],
        "answers": [
            "Para inquilinos: DNI o pasaporte y comprobante del teléfono declarado.",
            "La firma es electrónica y guardamos justificantes para su tranquilidad.",
        ],
    },
    "proceso": {
        "patterns": ["proceso", "como func", "cómo func", "pasos"],
        "answers": [
            "El proceso es simple: solicitud → verificación → contrato digital → entrada.",
            "Le guiamos en cada paso y resolvemos dudas en el momento.",
        ],
    },
    "pagos": {
        "patterns": ["pago", "stripe", "cobro", "tarjeta"],
        "answers": [
            "Los pagos son seguros con Stripe. La plataforma cobra y gestiona las transferencias.",
            "Propietarios y franquiciados reciben sus pagos según la política acordada.",
        ],
    },
    # Evitamos colisión con 'propietario' del flujo: patrones más explícitos
    "propietarios": {
        "patterns": ["info propietarios", "informacion propietarios", "para propietarios"],
        "answers": [
            "Para propietarios: publicamos, filtramos inquilinos, hacemos contrato y cobramos.",
            "Requisitos básicos: cerradura, cama 135×200 y buen estado.",
        ],
    },
    "soporte": {
        "patterns": ["soporte", "ayuda", "contacto", "telefono", "teléfono", "llamar", "asesor"],
        "answers": [
            "Tiene soporte durante la estancia por chat y teléfono.",
            "Si quiere, tomamos sus datos y le llama un asesor.",
        ],
    },
    "contrato": {
        "patterns": ["contrato", "logalty", "firma"],
        "answers": [
            "Los contratos se firman digitalmente con plena validez legal.",
            "Guardamos los justificantes para auditoría y tranquilidad de ambas partes.",
        ],
    },
}
