
# =============================================================================
# Este diccionario define, para cada propiedad del sistema, los valores
# esperados de los campos LOINC `property` y `scale_typ`.
#
# Sirve para dos propósitos en el endpoint _loinc_buscar:
#   1. FILTRADO: priorizar resultados que coincidan con estos atributos,
#      descartando LOINCs semánticamente incorrectos (ej. NFr cuando
#      se busca una concentración másica).
#   2. AUTO-ASIGNACIÓN: aumentar la confianza cuando todos los resultados
#      filtrados comparten el mismo property/scale esperado.
#
# Referencia de valores LOINC property más comunes en laboratorio:
#   MCnc  → Concentración másica          (g/dL, mg/L, µg/dL…)
#   SCnc  → Concentración de sustancia    (mmol/L, µmol/L…)
#   CCnc  → Concentración catalítica      (U/L, mU/L — enzimas)
#   ACnc  → Concentración arbitraria      (UI/mL, títulos)
#   NFr   → Fracción numérica             (%, ratio sin unidad)
#   NCnc  → Concentración numérica        (×10⁹/L, /µL — conteos)
#   Naric → Número aritmético             (conteos absolutos)
#   Time  → Tiempo                        (seg, min — coagulación)
#   Ratio → Razón / cociente              (INR, índices)
#   Type  → Tipo / clasificación          (grupo ABO, Rh — nominal)
#   Prid  → Identificador de presencia    (presente/ausente — Ord)
#   Arb   → Unidad arbitraria             (títulos de anticuerpos)
#
# Referencia de valores LOINC scale_typ:
#   Qn    → Cuantitativo (valor numérico continuo)
#   SemiQn→ Semi-cuantitativo (+, ++, +++…)
#   Ord   → Ordinal / cualitativo (Positivo/Negativo, Reactivo…)
#   Nom   → Nominal (grupo ABO, nombres de gérmenes)
#   Nar   → Narrativo (texto libre)
#
# NOTA: Usa listas para permitir más de un valor aceptable.
#       Si una propiedad puede ser Qn o Ord según el contexto,
#       incluye ambos.
# =============================================================================

# ---------------------------------------------------------------------------
# Tipo de muestra  →  valores del campo `system` en LoincCode
# ---------------------------------------------------------------------------
MUESTRA_A_LOINC_SYSTEM: dict[str, list[str]] = {
    # ── Sangre ──────────────────────────────────────────────────────────────
    'Sangre total con EDTA': [
        'Bld', 'BldA', 'BldC', 'BldMV', 'Bld+BldA', 'WBC',
    ],
    'Sangre total':          ['Bld', 'BldA'],
    'Sangre capilar':        ['Bld', 'BldC'],
    'Sangre arterial':       ['BldA'],
    'Sangre venosa':         ['BldV'],

    # ── Suero / Plasma ───────────────────────────────────────────────────────
    'Suero':                 ['Ser', 'Ser/Plas', 'Ser/Plas/Bld'],
    'Plasma con citrato':    ['Plas', 'PPP', 'PRP', 'Ser/Plas'],
    'Plasma con EDTA':       ['Plas', 'Ser/Plas'],
    'Plasma heparinizado':   ['Plas', 'Ser/Plas'],
    'Plasma':                ['Plas', 'Ser/Plas'],

    # ── Orina ────────────────────────────────────────────────────────────────
    'Orina aleatoria':       ['Urine', 'Ur', 'Urine+Ser/Plas'],
    'Orina de 24h':          ['Urine', 'Ur', 'Urine.spot+24H'],
    'Orina de 12h':          ['Urine', 'Ur'],
    'Orina primera mañana':  ['Urine.morning', 'Urine', 'Ur'],

    # ── LCR ─────────────────────────────────────────────────────────────────
    'Líquido cefalorraquídeo': ['CSF', 'CSF+Ser'],

    # ── Heces ────────────────────────────────────────────────────────────────
    'Heces':                 ['Stool', 'Feces'],

    # ── Exudados / Microbiología ─────────────────────────────────────────────
    'Exudado faríngeo':      ['Thrt', 'Throat'],
    'Exudado nasofaríngeo':  ['Nph', 'Nasoph'],
    'Exudado nasal':         ['Nose'],
    'Exudado vaginal':       ['Vag'],
    'Exudado uretral':       ['Urth'],
    'Exudado de herida':     ['Wound'],

    # ── Otros líquidos corporales ────────────────────────────────────────────
    'Líquido pleural':       ['Plr', 'Plr fld'],
    'Líquido ascítico':      ['Asc', 'Abd fld'],
    'Líquido sinovial':      ['Synv fld', 'Jt fld'],
    'Líquido pericárdico':   ['Pericard fld'],

    # ── Tejidos / Citología ──────────────────────────────────────────────────
    'Biopsia':               ['Tiss'],
    'Esputo':                ['Spt', 'Sputum'],
    'Lavado broncoalveolar': ['BAL', 'BronchWsh'],
}


# ---------------------------------------------------------------------------
# Método analítico  →  valores del campo `method_typ` en LoincCode
# ---------------------------------------------------------------------------
METODO_A_LOINC_METHOD: dict[str, list[str]] = {
    # ── Hematología ──────────────────────────────────────────────────────────
    'Impedancia eléctrica y microscópica': [
        'Automated count', 'Automated', 'Impedance', 'Machine count',
    ],
    'Impedancia eléctrica':  ['Automated count', 'Impedance', 'Automated'],
    'Microscópica':          ['Manual', 'Microscopy.light', 'Smear'],
    'Citometría de flujo':   ['Flow cytometry', 'Flow'],

    # ── Bioquímica ───────────────────────────────────────────────────────────
    'Espectrofotometría':    [
        'Spectrophotometry', 'Colorimetric', 'Enzymatic', 'Photometry',
        'Calculated',
    ],
    'Enzimático colorimétrico': ['Enzymatic', 'Colorimetric', 'Photometry'],
    'Turbidimetría':         ['Turbidimetry', 'Nephelometry'],
    'Inmunoturbidimetría':   ['Immunoturbidimetry', 'Turbidimetry', 'Nephelometry'],
    'Nefelometría':          ['Nephelometry', 'Immunoturbidimetry'],
    'Potenciometría':        ['Ion-selective electrode', 'ISE', 'Potentiometry'],
    'Electroforesis':        ['Electrophoresis', 'Electrop'],

    # ── Inmunoanálisis ───────────────────────────────────────────────────────
    'Electroquimioluminiscencia': [
        'Electrochemiluminescence immunoassay (ECLIA)',
        'Electrochemiluminescent immunoassay',
        'Chemiluminescent', 'ECLIA', 'CLIA',
    ],
    'Fluorescencia':         [
        'Immunofluorescence', 'IF', 'FEIA', 'FIA',
        'Fluorescent antibody',
    ],
    'Quimioluminiscencia':   ['Chemiluminescent', 'CLIA', 'ECLIA'],
    'ELISA':                 ['ELISA', 'EIA', 'Enzyme immunoassay'],
    'Aglutinación':          ['Agglutination', 'Latex agglutination', 'Aggl'],
    'Inmunoensayo':          ['Immunoassay', 'EIA', 'ELISA', 'CLIA'],
    'Western Blot':          ['Blot.western', 'Western blot', 'Immunoblot'],

    # ── Microbiología / Molecular ────────────────────────────────────────────
    'PCR':                   [
        'PCR', 'Probe.amp.tar', 'Probe and target amplification',
        'NAAT', 'Molecular',
    ],
    'PCR en tiempo real':    ['PCR', 'Probe.amp.tar', 'RT-PCR', 'NAAT'],
    'Cultivo microbiológico': ['Culture', 'Organism specific culture'],
    'Tinción de Gram':       ['Gram stain', 'Stain.gram'],
    'Tinción de Ziehl-Neelsen': ['Acid fast stain', 'AFB stain'],

    # ── Coagulación ──────────────────────────────────────────────────────────
    'Coagulométrico':        ['Coagulation', 'Clot detection', 'Optical'],
    'Cromogénico':           ['Chromogenic', 'Chromogenic substrate'],

    # ── Gasometría ───────────────────────────────────────────────────────────
    'Gasometría / electrodos específicos': [
        'Ion-selective electrode', 'ISE', 'Calculated', 'Electrode',
    ],

    # ── Urianálisis ──────────────────────────────────────────────────────────
    'Tira reactiva':         ['Test strip', 'Dipstick', 'Strip'],
    'Microscopia urinaria':  ['Microscopy.light', 'Manual', 'Automated'],
}


# ---------------------------------------------------------------------------
# Índices de búsqueda insensibles a mayúsculas (se construyen una sola vez)
# ---------------------------------------------------------------------------

_MUESTRA_INDEX: dict[str, list[str]] = {
    k.lower(): v for k, v in MUESTRA_A_LOINC_SYSTEM.items()
}

_METODO_INDEX: dict[str, list[str]] = {
    k.lower(): v for k, v in METODO_A_LOINC_METHOD.items()
}


# ---------------------------------------------------------------------------
# Helpers para el endpoint
# ---------------------------------------------------------------------------

def system_terms_for(tipo_muestra: str) -> list[str]:
    """
    Devuelve los términos LOINC system para el tipo_muestra dado.

    Estrategia de búsqueda (de más a menos específica):
    1. Coincidencia exacta (preserva capitalización original).
    2. Coincidencia insensible a mayúsculas/minúsculas.
    3. Coincidencia parcial: el tipo_muestra empieza por alguna clave conocida
       (ej. "Sangre total con heparina" → clave "Sangre total").
    Retorna lista vacía si no hay ningún mapeo (el filtro se ignorará).
    """
    key = tipo_muestra.strip()
    if not key:
        return []

    # 1. Exacto
    if key in MUESTRA_A_LOINC_SYSTEM:
        return MUESTRA_A_LOINC_SYSTEM[key]

    # 2. Case-insensitive exacto
    key_lower = key.lower()
    if key_lower in _MUESTRA_INDEX:
        return _MUESTRA_INDEX[key_lower]

    # 3. Coincidencia parcial (el valor enviado empieza por la clave)
    for k_lower, v in _MUESTRA_INDEX.items():
        if key_lower.startswith(k_lower):
            return v

    return []


def method_terms_for(metodo: str) -> list[str]:
    """
    Devuelve los términos LOINC method_typ para el método dado.

    Misma estrategia de 3 pasos que system_terms_for.
    Retorna lista vacía si no hay mapeo (el filtro se ignorará).
    """
    key = metodo.strip()
    if not key:
        return []

    # 1. Exacto
    if key in METODO_A_LOINC_METHOD:
        return METODO_A_LOINC_METHOD[key]

    # 2. Case-insensitive exacto
    key_lower = key.lower()
    if key_lower in _METODO_INDEX:
        return _METODO_INDEX[key_lower]

    # 3. Coincidencia parcial
    for k_lower, v in _METODO_INDEX.items():
        if key_lower.startswith(k_lower):
            return v

    return []


# ---------------------------------------------------------------------------
# Nombre de propiedad en español  →  términos de búsqueda en inglés
# para los campos `shortname` y `component` de LoincCode.
#
# LOINC almacena sus nombres en inglés, pero tus propiedades están en
# español. Este mapeo traduce el nombre antes de buscar en la BD.
#
# Reglas:
#   - La clave es el nombre exacto (o parte del nombre) de tu Propiedad
#     tal como está guardada en la BD.
#   - El valor es una lista de términos inglés que LOINC usa para ese
#     analito. Se hace OR entre ellos, igual que en system/method.
#   - Si el nombre español ya funciona en inglés (ej. "Glucosa"→"Glucose")
#     pon solo el término inglés principal.
# ---------------------------------------------------------------------------
NOMBRE_A_LOINC_COMPONENT: dict[str, list[str]] = {

    # ── Hematología — Serie Roja ─────────────────────────────────────────────
    'Eritrocitos':                   ['Erythrocytes', 'RBC', 'Red blood cells'],
    'Hemoglobina':                   ['Hemoglobin', 'Hgb', 'Hb'],
    'Hematocrito':                   ['Hematocrit', 'Hct', 'PCV'],
    'Volumen Corpuscular Medio':      ['MCV', 'Mean corpuscular volume'],
    'Volumen Globular Medio':         ['MCV', 'Mean corpuscular volume'],
    'Hemoglobina Corpuscular Media':  ['MCH', 'Mean corpuscular hemoglobin'],
    'Concentración de Hemoglobina Corpuscular Media': [
        'MCHC', 'Mean corpuscular hemoglobin concentration',
    ],
    'Amplitud de Distribución Eritrocitaria': ['RDW', 'Erythrocyte distribution width'],
    'RDW':                           ['RDW', 'Erythrocyte distribution width'],

    # ── Hematología — Serie Blanca ───────────────────────────────────────────
    'Leucocitos':                    ['Leukocytes', 'WBC', 'White blood cells'],
    'Neutrófilos':                   ['Neutrophils', 'Neutrophil'],
    'Linfocitos':                    ['Lymphocytes', 'Lymphocyte'],
    'Monocitos':                     ['Monocytes', 'Monocyte'],
    'Eosinófilos':                   ['Eosinophils', 'Eosinophil'],
    'Basófilos':                     ['Basophils', 'Basophil'],
    'Bandas':                        ['Band neutrophils', 'Bands'],
    'Metamielocitos':                ['Metamyelocytes'],
    'Mielocitos':                    ['Myelocytes'],

    # ── Hematología — Plaquetas ──────────────────────────────────────────────
    'Plaquetas':                     ['Platelets', 'PLT', 'Thrombocytes'],
    'Volumen Plaquetario Medio':     ['MPV', 'Mean platelet volume'],
    'MPV':                           ['MPV', 'Mean platelet volume'],

    # ── Química sanguínea ────────────────────────────────────────────────────
    'Glucosa':                       ['Glucose'],
    'Urea':                          ['Urea', 'BUN', 'Blood urea nitrogen'],
    'Creatinina':                    ['Creatinine'],
    'Ácido Úrico':                   ['Urate', 'Uric acid'],
    'Colesterol Total':              ['Cholesterol', 'Total cholesterol'],
    'Colesterol HDL':                ['HDL', 'High density lipoprotein'],
    'Colesterol LDL':                ['LDL', 'Low density lipoprotein'],
    'Triglicéridos':                 ['Triglycerides', 'Triglyceride'],
    'Proteínas Totales':             ['Protein', 'Total protein'],
    'Albúmina':                      ['Albumin'],
    'Globulinas':                    ['Globulin'],
    'Bilirrubina Total':             ['Bilirubin', 'Total bilirubin'],
    'Bilirrubina Directa':           ['Bilirubin.direct', 'Direct bilirubin', 'Conjugated bilirubin'],
    'Bilirrubina Indirecta':         ['Bilirubin.indirect', 'Indirect bilirubin'],
    'TGO':                           ['AST', 'Aspartate aminotransferase', 'SGOT'],
    'TGP':                           ['ALT', 'Alanine aminotransferase', 'SGPT'],
    'Fosfatasa Alcalina':            ['Alkaline phosphatase', 'ALP'],
    'GGT':                           ['GGT', 'Gamma glutamyl transferase'],
    'LDH':                           ['LDH', 'Lactate dehydrogenase'],
    'CPK':                           ['CPK', 'Creatine kinase', 'CK'],
    'Amilasa':                       ['Amylase'],
    'Lipasa':                        ['Lipase'],
    'Calcio':                        ['Calcium'],
    'Fósforo':                       ['Phosphate', 'Phosphorus'],
    'Magnesio':                      ['Magnesium'],
    'Sodio':                         ['Sodium'],
    'Potasio':                       ['Potassium'],
    'Cloro':                         ['Chloride'],
    'Bicarbonato':                   ['Bicarbonate', 'HCO3'],
    'Hierro':                        ['Iron', 'Fe'],
    'Ferritina':                     ['Ferritin'],
    'Transferrina':                  ['Transferrin'],
    'Vitamina B12':                  ['Vitamin B12', 'Cobalamin'],
    'Ácido Fólico':                  ['Folate', 'Folic acid'],

    # ── Hormonas tiroideas ───────────────────────────────────────────────────
    'TSH':                           ['TSH', 'Thyrotropin', 'Thyroid stimulating hormone'],
    'T3 Total':                      ['Triiodothyronine', 'T3'],
    'T3 Libre':                      ['Triiodothyronine.free', 'Free T3'],
    'T4 Total':                      ['Thyroxine', 'T4'],
    'T4 Libre':                      ['Thyroxine.free', 'Free T4'],

    # ── Hormonas reproductivas ───────────────────────────────────────────────
    'FSH':                           ['FSH', 'Follitropin', 'Follicle stimulating hormone'],
    'LH':                            ['LH', 'Lutropin', 'Luteinizing hormone'],
    'Prolactina':                    ['Prolactin'],
    'Estradiol':                     ['Estradiol'],
    'Progesterona':                  ['Progesterone'],
    'Testosterona':                  ['Testosterone'],
    'HCG':                           ['Choriogonadotropin', 'HCG', 'Beta HCG'],

    # ── Marcadores tumorales ─────────────────────────────────────────────────
    'PSA Total':                     ['PSA', 'Prostate specific antigen'],
    'PSA Libre':                     ['PSA.free', 'Free PSA'],
    'AFP':                           ['AFP', 'Alpha fetoprotein'],
    'CEA':                           ['CEA', 'Carcinoembryonic antigen'],
    'CA 125':                        ['CA125', 'Cancer antigen 125'],
    'CA 19-9':                       ['CA19-9', 'Cancer antigen 19-9'],

    # ── Coagulación ──────────────────────────────────────────────────────────
    'Tiempo de Protrombina':         ['Prothrombin', 'PT', 'INR'],
    'TP':                            ['Prothrombin', 'PT'],
    'INR':                           ['INR', 'International normalized ratio'],
    'TTP':                           ['Partial thromboplastin', 'PTT', 'APTT'],
    'Fibrinógeno':                   ['Fibrinogen'],
    'Dímero D':                      ['D-dimer', 'Fibrin D-dimer'],

    # ── Urianálisis ──────────────────────────────────────────────────────────
    'pH Urinario':                   ['pH', 'Hydrogen ion'],
    'Densidad Urinaria':             ['Specific gravity', 'Density'],
    'Proteínas en Orina':            ['Protein', 'Albumin'],
    'Glucosa en Orina':              ['Glucose'],
    'Cetonas':                       ['Ketones', 'Acetone'],
    'Sangre en Orina':               ['Blood', 'Hemoglobin'],
    'Nitritos':                      ['Nitrite'],
    'Leucocitos en Orina':           ['Leukocytes', 'WBC'],

    # ── Inmunología / Serología ──────────────────────────────────────────────
    'PCR (Proteína C Reactiva)':     ['C reactive protein', 'CRP'],
    'Proteína C Reactiva':           ['C reactive protein', 'CRP'],
    'Factor Reumatoide':             ['Rheumatoid factor', 'RF'],
    'ANA':                           ['ANA', 'Antinuclear antibody'],
    'ASTO':                          ['Antistreptolysin', 'ASO', 'ASTO'],
    'IgA':                           ['IgA', 'Immunoglobulin A'],
    'IgG':                           ['IgG', 'Immunoglobulin G'],
    'IgM':                           ['IgM', 'Immunoglobulin M'],
    'IgE':                           ['IgE', 'Immunoglobulin E'],

    # ── Hemoglobina glicosilada ──────────────────────────────────────────────
    'Hemoglobina Glicosilada':       ['Hemoglobin A1c', 'HbA1c', 'Glycated hemoglobin'],
    'HbA1c':                         ['Hemoglobin A1c', 'HbA1c'],
}


# Índice insensible a mayúsculas/minúsculas
_NOMBRE_INDEX: dict[str, list[str]] = {
    k.lower(): v for k, v in NOMBRE_A_LOINC_COMPONENT.items()
}


def component_terms_for(nombre_propiedad: str) -> list[str]:
    """
    Traduce el nombre de propiedad en español a términos de búsqueda
    en inglés para los campos shortname/component de LoincCode.

    Estrategia (igual que las otras funciones):
    1. Coincidencia exacta.
    2. Case-insensitive exacto.
    3. Coincidencia parcial (el nombre empieza por alguna clave).
    4. Si no hay mapeo, devuelve el nombre original tal cual
       (por si ya está en inglés o es un código numérico).
    """
    import re
    key = nombre_propiedad.strip()
    if not key:
        return []

    # 0. Si parece un código LOINC numérico (ej. "718", "2345-7"),
    #    devolverlo tal cual — solo tiene sentido buscarlo en loinc_num.
    if re.match(r'^\d[\d\-]*$', key):
        return [key]

    # 1. Exacto
    if key in NOMBRE_A_LOINC_COMPONENT:
        return NOMBRE_A_LOINC_COMPONENT[key]

    # 2. Case-insensitive exacto
    key_lower = key.lower()
    if key_lower in _NOMBRE_INDEX:
        return _NOMBRE_INDEX[key_lower]

    # 3. Coincidencia parcial
    for k_lower, v in _NOMBRE_INDEX.items():
        if key_lower.startswith(k_lower) or k_lower.startswith(key_lower):
            return v

    # 4. Sin mapeo en el diccionario → devolver el nombre original + los primeros
    #    4 caracteres como término adicional.
    #
    #    Justificación: muchos analitos comparten raíz entre español e inglés
    #    ("Gluc" → Glucose, "Trigl" → Triglycerides, "Bili" → Bilirubin, etc.),
    #    por lo que buscar el prefijo amplía la cobertura para propiedades
    #    que aún no están en el diccionario NOMBRE_A_LOINC_COMPONENT.
    #
    #    No funciona para raíces distintas (Sodio/Sodium, Hierro/Iron, etc.):
    #    esos términos ya están en el diccionario, por lo que el fallback
    #    solo se usa para nombres desconocidos donde el riesgo es controlado.
    prefix4 = key_lower[:4]
    terms = [key]
    if len(key) > 4 and prefix4 not in key_lower[4:]:
        # Solo agregar el prefijo si aporta algo (no si el nombre ya es corto)
        terms.append(prefix4)
    return terms


NOMBRE_A_LOINC_ATTRS: dict[str, dict[str, list[str]]] = {

    # ── Hematología — Serie Roja ─────────────────────────────────────────────
    'Eritrocitos':                    {'property': ['NCnc'],        'scale': ['Qn']},
    'Hemoglobina':                    {'property': ['MCnc'],        'scale': ['Qn']},
    'Hematocrito':                    {'property': ['NFr'],         'scale': ['Qn']},
    'Volumen Corpuscular Medio':       {'property': ['EntVol'],      'scale': ['Qn']},
    'Volumen Globular Medio':          {'property': ['EntVol'],      'scale': ['Qn']},
    'Hemoglobina Corpuscular Media':   {'property': ['EntMass'],     'scale': ['Qn']},
    'Concentración de Hemoglobina Corpuscular Media': {
                                       'property': ['MCnc'],        'scale': ['Qn']},
    'Amplitud de Distribución Eritrocitaria': {
                                       'property': ['NFr', 'EntVol'], 'scale': ['Qn']},
    'RDW':                             {'property': ['NFr', 'EntVol'], 'scale': ['Qn']},

    # ── Hematología — Serie Blanca ───────────────────────────────────────────
    # NCnc = concentración numérica (×10⁹/L); NFr = fracción (%) del diferencial
    'Leucocitos':                      {'property': ['NCnc'],        'scale': ['Qn']},
    'Neutrófilos':                     {'property': ['NCnc', 'NFr'], 'scale': ['Qn']},
    'Linfocitos':                      {'property': ['NCnc', 'NFr'], 'scale': ['Qn']},
    'Monocitos':                       {'property': ['NCnc', 'NFr'], 'scale': ['Qn']},
    'Eosinófilos':                     {'property': ['NCnc', 'NFr'], 'scale': ['Qn']},
    'Basófilos':                       {'property': ['NCnc', 'NFr'], 'scale': ['Qn']},
    'Bandas':                          {'property': ['NCnc', 'NFr'], 'scale': ['Qn']},
    'Metamielocitos':                  {'property': ['NCnc', 'NFr'], 'scale': ['Qn']},
    'Mielocitos':                      {'property': ['NCnc', 'NFr'], 'scale': ['Qn']},

    # ── Hematología — Plaquetas ──────────────────────────────────────────────
    'Plaquetas':                       {'property': ['NCnc'],        'scale': ['Qn']},
    'Volumen Plaquetario Medio':        {'property': ['EntVol'],      'scale': ['Qn']},
    'MPV':                             {'property': ['EntVol'],      'scale': ['Qn']},

    # ── Química sanguínea — concentraciones básicas (g/dL, mg/dL) ───────────
    'Glucosa':                         {'property': ['MCnc', 'SCnc'], 'scale': ['Qn']},
    'Urea':                            {'property': ['MCnc', 'SCnc'], 'scale': ['Qn']},
    'Creatinina':                      {'property': ['MCnc', 'SCnc'], 'scale': ['Qn']},
    'Ácido Úrico':                     {'property': ['MCnc', 'SCnc'], 'scale': ['Qn']},
    'Colesterol Total':                {'property': ['MCnc', 'SCnc'], 'scale': ['Qn']},
    'Colesterol HDL':                  {'property': ['MCnc', 'SCnc'], 'scale': ['Qn']},
    'Colesterol LDL':                  {'property': ['MCnc', 'SCnc'], 'scale': ['Qn']},
    'Triglicéridos':                   {'property': ['MCnc', 'SCnc'], 'scale': ['Qn']},
    'Proteínas Totales':               {'property': ['MCnc'],         'scale': ['Qn']},
    'Albúmina':                        {'property': ['MCnc'],         'scale': ['Qn']},
    'Globulinas':                      {'property': ['MCnc'],         'scale': ['Qn']},
    'Bilirrubina Total':               {'property': ['MCnc', 'SCnc'], 'scale': ['Qn']},
    'Bilirrubina Directa':             {'property': ['MCnc', 'SCnc'], 'scale': ['Qn']},
    'Bilirrubina Indirecta':           {'property': ['MCnc', 'SCnc'], 'scale': ['Qn']},
    'Calcio':                          {'property': ['MCnc', 'SCnc'], 'scale': ['Qn']},
    'Fósforo':                         {'property': ['MCnc', 'SCnc'], 'scale': ['Qn']},
    'Magnesio':                        {'property': ['MCnc', 'SCnc'], 'scale': ['Qn']},
    'Sodio':                           {'property': ['SCnc'],         'scale': ['Qn']},
    'Potasio':                         {'property': ['SCnc'],         'scale': ['Qn']},
    'Cloro':                           {'property': ['SCnc'],         'scale': ['Qn']},
    'Bicarbonato':                     {'property': ['SCnc'],         'scale': ['Qn']},
    'Hierro':                          {'property': ['MCnc', 'SCnc'], 'scale': ['Qn']},
    'Ferritina':                       {'property': ['MCnc'],         'scale': ['Qn']},
    'Transferrina':                    {'property': ['MCnc'],         'scale': ['Qn']},
    'Vitamina B12':                    {'property': ['MCnc', 'SCnc'], 'scale': ['Qn']},
    'Ácido Fólico':                    {'property': ['MCnc', 'SCnc'], 'scale': ['Qn']},

    # ── Enzimas hepáticas / musculares — actividad catalítica (U/L) ──────────
    # CCnc es el property correcto para actividad enzimática, no MCnc
    'TGO':                             {'property': ['CCnc'],         'scale': ['Qn']},
    'TGP':                             {'property': ['CCnc'],         'scale': ['Qn']},
    'Fosfatasa Alcalina':              {'property': ['CCnc'],         'scale': ['Qn']},
    'GGT':                             {'property': ['CCnc'],         'scale': ['Qn']},
    'LDH':                             {'property': ['CCnc'],         'scale': ['Qn']},
    'CPK':                             {'property': ['CCnc'],         'scale': ['Qn']},
    'Amilasa':                         {'property': ['CCnc'],         'scale': ['Qn']},
    'Lipasa':                          {'property': ['CCnc'],         'scale': ['Qn']},

    # ── Hormonas tiroideas ───────────────────────────────────────────────────
    # MCnc para las que se miden en masa (µg/dL, ng/dL)
    # ACnc para TSH (unidades arbitrarias mUI/L)
    'TSH':                             {'property': ['ACnc'],         'scale': ['Qn']},
    'T3 Total':                        {'property': ['MCnc', 'SCnc'], 'scale': ['Qn']},
    'T3 Libre':                        {'property': ['MCnc', 'SCnc'], 'scale': ['Qn']},
    'T4 Total':                        {'property': ['MCnc', 'SCnc'], 'scale': ['Qn']},
    'T4 Libre':                        {'property': ['MCnc', 'SCnc'], 'scale': ['Qn']},

    # ── Hormonas reproductivas ───────────────────────────────────────────────
    'FSH':                             {'property': ['ACnc'],         'scale': ['Qn']},
    'LH':                              {'property': ['ACnc'],         'scale': ['Qn']},
    'Prolactina':                      {'property': ['MCnc', 'ACnc'], 'scale': ['Qn']},
    'Estradiol':                       {'property': ['MCnc', 'SCnc'], 'scale': ['Qn']},
    'Progesterona':                    {'property': ['MCnc', 'SCnc'], 'scale': ['Qn']},
    'Testosterona':                    {'property': ['MCnc', 'SCnc'], 'scale': ['Qn']},
    'HCG':                             {'property': ['ACnc'],         'scale': ['Qn']},

    # ── Marcadores tumorales ─────────────────────────────────────────────────
    'PSA Total':                       {'property': ['MCnc', 'ACnc'], 'scale': ['Qn']},
    'PSA Libre':                       {'property': ['MCnc', 'ACnc'], 'scale': ['Qn']},
    'AFP':                             {'property': ['MCnc', 'ACnc'], 'scale': ['Qn']},
    'CEA':                             {'property': ['MCnc', 'ACnc'], 'scale': ['Qn']},
    'CA 125':                          {'property': ['ACnc'],         'scale': ['Qn']},
    'CA 19-9':                         {'property': ['ACnc'],         'scale': ['Qn']},

    # ── Coagulación ──────────────────────────────────────────────────────────
    'Tiempo de Protrombina':           {'property': ['Time'],         'scale': ['Qn']},
    'TP':                              {'property': ['Time'],         'scale': ['Qn']},
    'INR':                             {'property': ['Ratio'],        'scale': ['Qn']},
    'TTP':                             {'property': ['Time'],         'scale': ['Qn']},
    'Fibrinógeno':                     {'property': ['MCnc'],         'scale': ['Qn']},
    'Dímero D':                        {'property': ['MCnc', 'ACnc'], 'scale': ['Qn']},

    # ── Inmunología / Serología ──────────────────────────────────────────────
    # MCnc para cuantitativas en mg/dL; ACnc para títulos/unidades arbitrarias
    # Ord para las puramente cualitativas (Reactivo/No Reactivo)
    'PCR (Proteína C Reactiva)':       {'property': ['MCnc'],         'scale': ['Qn']},
    'Proteína C Reactiva':             {'property': ['MCnc'],         'scale': ['Qn']},
    'Factor Reumatoide':               {'property': ['ACnc', 'MCnc'], 'scale': ['Qn', 'Ord']},
    'ANA':                             {'property': ['ACnc', 'Titr'], 'scale': ['Qn', 'Ord']},
    'ASTO':                            {'property': ['ACnc'],         'scale': ['Qn', 'Ord']},
    'IgA':                             {'property': ['MCnc'],         'scale': ['Qn']},
    'IgG':                             {'property': ['MCnc'],         'scale': ['Qn']},
    'IgM':                             {'property': ['MCnc'],         'scale': ['Qn']},
    'IgE':                             {'property': ['ACnc'],         'scale': ['Qn']},

    # ── Hemoglobina glicosilada ──────────────────────────────────────────────
    'Hemoglobina Glicosilada':         {'property': ['NFr'],          'scale': ['Qn']},
    'HbA1c':                           {'property': ['NFr'],          'scale': ['Qn']},

    # ── Urianálisis cuantitativos ────────────────────────────────────────────
    'pH Urinario':                     {'property': ['SCnc'],         'scale': ['Qn']},
    'Densidad Urinaria':               {'property': ['RelMCnc'],      'scale': ['Qn']},
    'Proteínas en Orina':              {'property': ['MCnc', 'MRat'], 'scale': ['Qn']},
    'Glucosa en Orina':                {'property': ['MCnc', 'SCnc'], 'scale': ['Qn', 'Ord']},
    'Cetonas':                         {'property': ['MCnc'],         'scale': ['Qn', 'Ord']},
    'Sangre en Orina':                 {'property': ['NCnc'],         'scale': ['Qn', 'Ord']},
    'Nitritos':                        {'property': ['Prid'],         'scale': ['Ord']},
    'Leucocitos en Orina':             {'property': ['NCnc'],         'scale': ['Qn', 'Ord']},
}


# Índice insensible a mayúsculas para búsqueda rápida
_ATTRS_INDEX: dict[str, dict[str, list[str]]] = {
    k.lower(): v for k, v in NOMBRE_A_LOINC_ATTRS.items()
}


def attrs_for(nombre_propiedad: str) -> dict[str, list[str]]:
    """
    Devuelve los atributos LOINC esperados (property, scale_typ) para
    el nombre de propiedad dado.

    Retorna un dict con las claves 'property' y 'scale', cada una
    con una lista de valores aceptables (OR entre ellos).
    Retorna dict vacío si no hay mapeo definido para esa propiedad.

    Estrategia de búsqueda:
    1. Exacto con el nombre original.
    2. Exacto con el nombre limpio (sin prefijo # o %).
    3. Case-insensitive exacto (original y limpio).
    4. Coincidencia parcial con el nombre limpio.

    NOTA sobre prefijos de símbolo:
        Propiedades como '%MONOCITOS' (#→conteo, %→porcentaje) usan un
        prefijo para diferenciar dos variantes del mismo analito.
        Esta función ignora el prefijo en la búsqueda del diccionario.
        La interpretación semántica del prefijo (NFr vs NCnc) la hace
        _loinc_buscar() en admin.py, que tiene prioridad sobre este dict.
    """
    import re as _re

    key = nombre_propiedad.strip()
    if not key:
        return {}

    # Nombre sin prefijo # / % para la búsqueda en el diccionario
    key_clean = _re.sub(r'^[#%]+', '', key).strip()

    # 1. Exacto con nombre original
    if key in NOMBRE_A_LOINC_ATTRS:
        return NOMBRE_A_LOINC_ATTRS[key]

    # 2. Exacto con nombre limpio (cubre '%MONOCITOS' → 'MONOCITOS')
    if key_clean and key_clean in NOMBRE_A_LOINC_ATTRS:
        return NOMBRE_A_LOINC_ATTRS[key_clean]

    # 3. Case-insensitive exacto
    key_lower       = key.lower()
    key_clean_lower = key_clean.lower()

    if key_lower in _ATTRS_INDEX:
        return _ATTRS_INDEX[key_lower]
    if key_clean_lower and key_clean_lower in _ATTRS_INDEX:
        return _ATTRS_INDEX[key_clean_lower]

    # 4. Coincidencia parcial con el nombre limpio
    for k_lower, v in _ATTRS_INDEX.items():
        if key_clean_lower.startswith(k_lower) or k_lower.startswith(key_clean_lower):
            return v

    # Sin mapeo: no restringir (el endpoint usará solo component/system/method)
    return {}
