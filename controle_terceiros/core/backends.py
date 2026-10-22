"""Acesso físico aos dados.

- GSheetsBackend: usa uma planilha Google (uma aba por tabela).
- LocalBackend: grava arquivos CSV na pasta `dados_local/` — útil para testar
  no computador sem configurar o Google.

Os dois têm a mesma interface, então o resto do sistema não sabe (nem precisa
saber) onde os dados estão.
"""
from __future__ import annotations

import os
import datetime as dt

import pandas as pd


def _valor(v):
    """Converte um valor Python/pandas em algo gravável (texto ou número)."""
    if v is None:
        return ""
    try:
        if pd.isna(v):
            return ""
    except (TypeError, ValueError):
        pass
    if isinstance(v, (pd.Timestamp, dt.datetime)):
        return v.strftime("%Y-%m-%d %H:%M:%S") if (v.hour or v.minute or v.second) else v.strftime("%Y-%m-%d")
    if isinstance(v, dt.date):
        return v.isoformat()
    if hasattr(v, "item"):          # tipos numpy
        v = v.item()
    if isinstance(v, float) and v.is_integer():
        return int(v)
    return v


class LocalBackend:
    nome = "Local (CSV)"

    def __init__(self, pasta: str = "dados_local"):
        self.pasta = pasta
        os.makedirs(pasta, exist_ok=True)

    def _arq(self, tabela):
        return os.path.join(self.pasta, f"{tabela}.csv")

    def garantir(self, tabela, colunas):
        if not os.path.exists(self._arq(tabela)):
            pd.DataFrame(columns=colunas).to_csv(self._arq(tabela), index=False)

    def ler(self, tabela, colunas) -> pd.DataFrame:
        self.garantir(tabela, colunas)
        df = pd.read_csv(self._arq(tabela), dtype=str, keep_default_na=False)
        for c in colunas:
            if c not in df.columns:
                df[c] = ""
        return df[colunas]

    def _gravar(self, tabela, df):
        df.to_csv(self._arq(tabela), index=False)

    def anexar(self, tabela, colunas, linhas: list[dict]):
        df = self.ler(tabela, colunas)
        novas = pd.DataFrame([{c: _valor(l.get(c, "")) for c in colunas} for l in linhas], dtype=str)
        self._gravar(tabela, pd.concat([df, novas], ignore_index=True))

    def atualizar(self, tabela, colunas, chave, valor, mudancas: dict):
        df = self.ler(tabela, colunas)
        idx = df.index[df[chave] == str(valor)]
        if len(idx) == 0:
            raise KeyError(f"Registro {valor} não encontrado em {tabela}")
        for c, v in mudancas.items():
            df.loc[idx[0], c] = str(_valor(v))
        self._gravar(tabela, df)

    def excluir(self, tabela, colunas, chave, valor):
        df = self.ler(tabela, colunas)
        self._gravar(tabela, df[df[chave] != str(valor)])

    def substituir_tudo(self, tabela, colunas, df_novo: pd.DataFrame):
        out = pd.DataFrame({c: df_novo[c].map(_valor) if c in df_novo else "" for c in colunas})
        self._gravar(tabela, out)


class GSheetsBackend:
    nome = "Google Sheets"

    def __init__(self, credenciais: dict, planilha: str):
        import gspread  # importado aqui para o modo local funcionar sem a lib
        self._gspread = gspread
        gc = gspread.service_account_from_dict(credenciais)
        self.sh = gc.open_by_url(planilha) if planilha.startswith("http") else gc.open_by_key(planilha)
        self._abas = {}

    def _aba(self, tabela, colunas):
        if tabela in self._abas:
            return self._abas[tabela]
        try:
            ws = self.sh.worksheet(tabela)
        except self._gspread.WorksheetNotFound:
            ws = self.sh.add_worksheet(title=tabela, rows=1000, cols=max(len(colunas), 10))
        cab = ws.row_values(1)
        faltando = [c for c in colunas if c not in cab]
        if faltando:
            cab = cab + faltando
            if len(cab) > ws.col_count:
                ws.add_cols(len(cab) - ws.col_count)
            ws.update(range_name="A1", values=[cab], value_input_option="RAW")
            ws.freeze(rows=1)
        self._abas[tabela] = (ws, cab)
        return ws, cab

    def garantir(self, tabela, colunas):
        self._aba(tabela, colunas)

    def ler(self, tabela, colunas) -> pd.DataFrame:
        ws, cab = self._aba(tabela, colunas)
        valores = ws.get_all_values()
        if len(valores) <= 1:
            return pd.DataFrame(columns=colunas, dtype=str)
        largura = len(valores[0])
        linhas = [l + [""] * (largura - len(l)) for l in valores[1:]]
        df = pd.DataFrame(linhas, columns=valores[0], dtype=str)
        df = df[(df != "").any(axis=1)]
        for c in colunas:
            if c not in df.columns:
                df[c] = ""
        return df[colunas].reset_index(drop=True)

    def anexar(self, tabela, colunas, linhas: list[dict]):
        ws, cab = self._aba(tabela, colunas)
        ws.append_rows([[_valor(l.get(c, "")) for c in cab] for l in linhas],
                       value_input_option="RAW", table_range="A1")

    def _linha(self, ws, cab, chave, valor):
        col = cab.index(chave) + 1
        valores = ws.col_values(col)
        try:
            return valores.index(str(valor)) + 1
        except ValueError:
            raise KeyError(f"Registro {valor} não encontrado")

    def atualizar(self, tabela, colunas, chave, valor, mudancas: dict):
        ws, cab = self._aba(tabela, colunas)
        n = self._linha(ws, cab, chave, valor)
        atual = ws.row_values(n)
        atual += [""] * (len(cab) - len(atual))
        for c, v in mudancas.items():
            atual[cab.index(c)] = _valor(v)
        ws.update(range_name=f"A{n}", values=[atual], value_input_option="RAW")

    def excluir(self, tabela, colunas, chave, valor):
        ws, cab = self._aba(tabela, colunas)
        ws.delete_rows(self._linha(ws, cab, chave, valor))

    def substituir_tudo(self, tabela, colunas, df_novo: pd.DataFrame):
        ws, cab = self._aba(tabela, colunas)
        corpo = [[_valor(r.get(c, "")) for c in cab] for r in df_novo.to_dict("records")]
        ws.clear()
        ws.update(range_name="A1", values=[cab] + corpo, value_input_option="RAW")
