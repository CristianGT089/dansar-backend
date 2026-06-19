"""Lógica de negocio del módulo financiero."""
from .data import (
    load_all, PYG_STRUCTURE, SALES_ACCOUNTS, SALES_CATEGORIES, MESES,
)


def _val_lm(df_lm, cuenta, pk):
    Q_MAP = {1:[1,2,3], 2:[4,5,6], 3:[7,8,9], 4:[10,11,12]}
    if pk.startswith("M"):
        mes  = int(pk[1:])
        mask = (df_lm["CUENTA"] == cuenta) & (df_lm["MES"] == mes)
        v    = float(df_lm.loc[mask, "SALDO"].sum())
        return -v if cuenta.startswith("4") else v
    q = int(pk[1:])
    return sum(_val_lm(df_lm, cuenta, f"M{m:02d}") for m in Q_MAP[q])


def _row_sum(src_dict, cuentas, pk):
    return sum(src_dict.get(c, {}).get(pk, 0.0) for c in cuentas)


def _sec_total(src_dict, df_lm, year, sec, pk):
    t, inside = 0.0, False
    for lvl, lbl, cuentas in PYG_STRUCTURE:
        if lvl == 0:
            if lbl == sec: inside = True
            elif inside:   break
        if inside and cuentas:
            if year == 2026:
                t += sum(_val_lm(df_lm, c, pk) for c in cuentas)
            else:
                t += _row_sum(src_dict, cuentas, pk)
    return t


def _get_val(pyg24, pyg25, df_lm, year, cuenta, pk):
    if year == 2026:
        return _val_lm(df_lm, cuenta, pk)
    src = pyg25 if year == 2025 else pyg24
    return src.get(cuenta, {}).get(pk, 0.0)


def _build_calcs(pyg24, pyg25, df_lm, year, pk):
    def sec(s): return _sec_total(pyg24 if year == 2024 else pyg25, df_lm, year, s, pk)
    ub  = sec("INGRESOS OPERACIONALES") + sec("COSTOS")
    uo  = ub  + sec("GASTOS OPERACIONALES")
    uan = uo  + sec("NO OPERACIONALES")
    un  = uan + sec("IMPUESTO RENTA")
    return ub, uo, uan, un


def build_pyg_rows(periods):
    """
    periods: list of (year, pk, col_label)
    Returns list of row dicts with _label, _level, and one key per col_label.
    """
    df, _, pyg24, pyg25, _ = load_all()
    df_lm = df[df["ANIO"] == 2026]

    def src(year): return pyg24 if year == 2024 else pyg25

    def val(year, cuenta, pk):
        return _get_val(pyg24, pyg25, df_lm, year, cuenta, pk)

    def row_sum(year, cuentas, pk):
        return sum(val(year, c, pk) for c in cuentas)

    def sec_total(year, sec, pk):
        return _sec_total(src(year), df_lm, year, sec, pk)

    rows = []
    for lvl, label, cuentas in PYG_STRUCTURE:
        if lvl == 0:
            inserts = {
                "GASTOS OPERACIONALES": "UTILIDAD BRUTA",
                "NO OPERACIONALES":     "UTILIDAD OPERACIONAL",
                "IMPUESTO RENTA":       "UTILIDAD ANTES IMPUESTOS",
            }
            if label in inserts:
                c = {"_label": inserts[label], "_level": -1}
                for y, pk, col in periods:
                    ub, uo, uan, _ = _build_calcs(pyg24, pyg25, df_lm, y, pk)
                    c[col] = ub if label == "GASTOS OPERACIONALES" else (uo if label == "NO OPERACIONALES" else uan)
                rows.append(c)

        row = {"_label": label, "_level": lvl}
        for y, pk, col in periods:
            if lvl == 0:
                row[col] = sec_total(y, label, pk)
            elif cuentas:
                row[col] = row_sum(y, cuentas, pk)
            else:
                row[col] = None
        rows.append(row)

    net = {"_label": "UTILIDAD NETA", "_level": -1}
    for y, pk, col in periods:
        _, _, _, un = _build_calcs(pyg24, pyg25, df_lm, y, pk)
        net[col] = un
    rows.append(net)

    return rows


def add_deltas(rows, pairs):
    for row in rows:
        for base_col, comp_col, delta_col in pairs:
            b, c = row.get(base_col), row.get(comp_col)
            if b and c is not None and b != 0:
                row[delta_col] = round((c - b) / abs(b) * 100, 1)
            else:
                row[delta_col] = None
    return rows


def get_kpis(periods):
    """Calcula los 4 KPIs principales del strip."""
    df, _, pyg24, pyg25, _ = load_all()
    df_lm = df[df["ANIO"] == 2026]

    def sec(year, s, pk):
        src = pyg24 if year == 2024 else pyg25
        return _sec_total(src, df_lm, year, s, pk)

    result = []
    for y, pk, label in periods:
        ing  = sec(y, "INGRESOS OPERACIONALES", pk)
        cos  = sec(y, "COSTOS", pk)
        ub   = ing + cos
        mg   = round(ub / ing * 100, 1) if ing else 0
        result.append({"label": label, "ingresos": ing, "utilidad_bruta": ub, "margen_bruto": mg})
    return result


def get_utility_cascade(periods):
    """Calcula la cascada de utilidades."""
    df, _, pyg24, pyg25, _ = load_all()
    df_lm = df[df["ANIO"] == 2026]

    def sec(year, s, pk):
        src = pyg24 if year == 2024 else pyg25
        return _sec_total(src, df_lm, year, s, pk)

    result = []
    for y, pk, label in periods:
        ing  = sec(y, "INGRESOS OPERACIONALES", pk)
        ub, uo, uan, un = _build_calcs(pyg24, pyg25, df_lm, y, pk)
        result.append({
            "label": label,
            "ingresos": ing,
            "utilidad_bruta": ub,
            "utilidad_operacional": uo,
            "utilidad_neta": un,
            "margen_bruta": round(ub / ing * 100, 1) if ing else 0,
            "margen_operacional": round(uo / ing * 100, 1) if ing else 0,
            "margen_neto": round(un / ing * 100, 1) if ing else 0,
        })
    return result


def get_sales_trend():
    """Tendencia mensual de ventas 2024 vs 2025."""
    df, _, pyg24, pyg25, lm_months_2026 = load_all()
    df_lm = df[df["ANIO"] == 2026]

    result = []
    for m in range(1, 13):
        pk = f"M{m:02d}"
        v24 = sum(pyg24.get(c, {}).get(pk, 0) for c in SALES_ACCOUNTS)
        v25 = sum(pyg25.get(c, {}).get(pk, 0) for c in SALES_ACCOUNTS)
        v26 = None
        if m in lm_months_2026:
            v26 = sum(
                abs(float(df_lm[(df_lm["CUENTA"] == c) & (df_lm["MES"] == m)]["SALDO"].sum()))
                for c in SALES_ACCOUNTS
            )
        result.append({"mes": MESES[m], "v2024": v24, "v2025": v25, "v2026": v26})
    return result


def get_sales_mix(year: int):
    """Mix de ventas por categoría para un año."""
    df, _, pyg24, pyg25, lm_months_2026 = load_all()
    df_lm = df[df["ANIO"] == 2026]

    src = pyg24 if year == 2024 else pyg25
    result = []
    for cat, accounts in SALES_CATEGORIES.items():
        if year == 2026:
            total = sum(
                abs(float(df_lm[df_lm["CUENTA"] == c]["SALDO"].sum()))
                for c in accounts
            )
        else:
            total = sum(sum(src.get(c, {}).get(f"M{m:02d}", 0) for m in range(1, 13)) for c in accounts)
        result.append({"categoria": cat, "valor": total})
    return result


def get_quarterly_sales():
    """Ventas por trimestre 2024 vs 2025."""
    _, _, pyg24, pyg25, _ = load_all()
    result = []
    for q in range(1, 5):
        pk = f"Q{q}"
        v24 = sum(pyg24.get(c, {}).get(pk, 0) for c in SALES_ACCOUNTS)
        v25 = sum(pyg25.get(c, {}).get(pk, 0) for c in SALES_ACCOUNTS)
        result.append({"trimestre": f"Q{q}", "v2024": v24, "v2025": v25})
    return result


def get_category_sales_ytd():
    """Ventas YTD 2026 por categoría."""
    df, _, _, _, lm_months_2026 = load_all()
    df_lm = df[df["ANIO"] == 2026]
    last_month = max(lm_months_2026) if lm_months_2026 else 0

    result = []
    for cat, accounts in SALES_CATEGORIES.items():
        total = sum(
            abs(float(df_lm[df_lm["CUENTA"] == c]["SALDO"].sum()))
            for c in accounts
        )
        result.append({"categoria": cat, "valor": total})
    return {"data": result, "last_month": MESES.get(last_month, "—")}


def get_libro_mayor(year=None, month=None, account=None, cost_center=None, page=1, page_size=50):
    df, cc_df, _, _, _ = load_all()
    q = df.copy()

    if year:    q = q[q["ANIO"] == year]
    if month:   q = q[q["MES"]  == month]
    if account: q = q[q["CUENTA"] == str(account)]
    if cost_center and cost_center != "Todos":
        q = q[q["CENTROCOSTE"] == str(cost_center)]

    q = q.sort_values(["ANIO", "MES", "CUENTA"]).head(500)
    total = len(q)
    start = (page - 1) * page_size
    page_df = q.iloc[start: start + page_size]

    cols_out = [c for c in ["ANIO","MES","CUENTA","TITULO","DEBE","HABER","SALDO","CENTROCOSTE"] if c in page_df.columns]
    records = page_df[cols_out].fillna(0).to_dict("records")

    centers = sorted(cc_df["CENTROCOSTE"].dropna().unique().tolist()) if cc_df is not None else []
    years   = sorted(df["ANIO"].dropna().unique().astype(int).tolist())

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "records": records,
        "centers": centers,
        "years": years,
    }


def get_meta():
    _, _, pyg24, pyg25, lm_months_2026 = load_all()
    return {
        "lm_months_2026": [MESES[m] for m in lm_months_2026],
        "pyg24_accounts": len(pyg24),
        "pyg25_accounts": len(pyg25),
    }
