<div align="center">

<img src="icono.png" alt="AdOps" width="110" />

# AdOps · Control Financiero

**Calculá, compará y auditá tus números de publicidad programática.**
Una app de escritorio liviana, sin instalaciones raras y sin dependencias.

<br />

![Python](https://img.shields.io/badge/Python-3.8%2B-2563EB?style=for-the-badge&logo=python&logoColor=white)
![GUI](https://img.shields.io/badge/GUI-tkinter%20%2B%20ttk-0F172A?style=for-the-badge)
![Dependencias](https://img.shields.io/badge/Dependencias-0-16A34A?style=for-the-badge)
![Plataforma](https://img.shields.io/badge/Windows%20%C2%B7%20macOS%20%C2%B7%20Linux-64748B?style=for-the-badge)

[Para quién es](#-para-quién-es) ·
[Qué incluye](#-qué-incluye) ·
[Inicio rápido](#-inicio-rápido) ·
[Fórmulas](#-fórmulas) ·
[Generar el .exe](#-generar-el-exe)

</div>

<br />

## ✦ Para quién es

AdOps está pensada para quienes trabajan con números de programática todos los días y no quieren armar una planilla nueva cada vez:

| Perfil | Para qué le sirve |
|---|---|
| **Ad Ops / Revenue Ops** | Pasar de CPM a revenue (y al revés) y ver el margen real en segundos |
| **Publishers** | Comparar fuentes de demanda por eCPM neto y detectar cuál rinde más |
| **Agencias y traders** | Entender cuánto del bruto llega al publisher y cuánto se queda el intermediario |
| **Finanzas y conciliación** | Cuantificar discrepancias contra el partner antes de facturar |

> Todo se calcula en tu computadora. No hay cuentas, ni servidores, ni datos que salgan de tu equipo.

<br />

## ✦ Qué incluye

El encabezado tiene dos controles globales:

- **Tipo de precio** · alterna entre *Bruto / Gross* y *Neto / Net*. Define cómo se interpretan los valores que cargás.
- **Limpiar / Cargar ejemplo** · carga datos de prueba en todas las pestañas o borra todo de una vez.

<br />

### 1 · Calculadora CPM / eCPM y Margen

Dos modos de trabajo, con un toggle:

| Modo | Tenés | Obtenés |
|---|---|---|
| **A** | CPM e impresiones | Revenue |
| **B** | Revenue e impresiones | eCPM |

Podés sumar un bloque opcional de **Intermediario** con CPM Bruto y Neto, o directamente un % de margen deseado.

**Resultado en cuatro tarjetas:** Revenue Bruto · Pago al Publisher (Neto) · Profit · Margen (%).
Debajo, un desglose con **la fórmula aplicada en cada línea** y un gráfico de barras que muestra el reparto Publisher vs Intermediario. Todo se recalcula mientras escribís.

<br />

### 2 · Comparador de Fuentes (eCPM y Embudo)

Cargá cada fuente con su embudo completo (Requests, Bids, Wins, Impresiones) y su precio. La app calcula por fila:

`Bid Rate` · `Win Rate` · `Render Rate` · `Fill Rate` · `eCPM Neto` · `Margen`

- La fuente más rentable queda **resaltada en verde con ★**.
- Un **ranking visual** ordena todas las fuentes por eCPM neto.
- **Exportación a CSV**, lista para abrir en Excel o Google Sheets.
- Validación del embudo: avisa si las cifras no son decrecientes (Requests ≥ Bids ≥ Wins ≥ Impresiones).

<details>
<summary><b>¿Qué significa "Modo de pago" y "Fee"?</b></summary>

<br />

- **CPM**: el valor que cargás es el precio por mil impresiones.
- **eCPM**: el valor que cargás es el revenue total; el eCPM se calcula solo.
- **Fee interm. (%)**: el margen del intermediario. Se usa para convertir entre Bruto y Neto según el tipo de precio de cada fuente.

</details>

<br />

### 3 · Control de Discrepancias

Compará tus impresiones contra las del partner (y, si querés, también el revenue) y obtené un diagnóstico al instante con un semáforo:

| Estado | Rango | Qué hacer |
|:---:|:---:|---|
| 🟢 **Normal** | ≤ 5% | Nada, está dentro de lo esperable |
| 🟡 **Tolerable** | 5% – 10% | Monitorear tendencia por día, placement y formato |
| 🔴 **Alerta** | > 10% | Revisar render, medición (ventana de conteo, viewability, zona horaria) e IVT |

El semáforo toma el mayor valor absoluto entre la discrepancia de impresiones y la de revenue. El botón **Cargar datos de prueba** rota entre un caso verde, uno amarillo y uno rojo para que veas los tres estados.

<br />

## ✦ Inicio rápido

**Requisitos:** Python 3.8 o superior con tkinter. En Windows y macOS ya viene incluido con el instalador de [python.org](https://www.python.org/downloads/).

```bash
python adops_control_financiero.py
```

> **Windows:** si `python` no se reconoce, usá `py adops_control_financiero.py`.
> **Linux:** si falta tkinter, instalalo con `sudo apt install python3-tk`.

Al abrir la app, tocá **Limpiar / Cargar ejemplo → Cargar ejemplo** y recorré las tres pestañas para ver todo funcionando.

<br />

## ✦ Fórmulas

Todas las fórmulas se muestran en pantalla para que puedas auditar cada resultado.

<details>
<summary><b>Calculadora</b></summary>

<br />

```
Revenue Bruto  = Impresiones ÷ 1.000 × CPM Bruto
Pago Publisher = Revenue Bruto × (1 − Margen)
Profit         = Revenue Bruto − Pago Publisher
Margen (%)     = Profit ÷ Revenue Bruto × 100
eCPM           = Revenue ÷ Impresiones × 1.000
```

Si el valor ingresado es **Neto**: `Bruto = Neto ÷ (1 − Margen)`.
El margen se toma de, en orden de prioridad: CPM Bruto y Neto del intermediario → % de margen deseado → un único CPM del intermediario contra el precio ingresado → 0%.

</details>

<details>
<summary><b>Comparador</b></summary>

<br />

```
Bid Rate    = Bids ÷ Requests × 100
Win Rate    = Wins ÷ Bids × 100
Render Rate = Impresiones ÷ Wins × 100
Fill Rate   = Impresiones ÷ Requests × 100
eCPM Neto   = Revenue Neto ÷ Impresiones × 1.000
Margen (%)  = (Bruto − Neto) ÷ Bruto × 100
```

</details>

<details>
<summary><b>Discrepancias</b></summary>

<br />

```
Diferencia absoluta = Impresiones Partner − Impresiones Propias
Discrepancia (%)    = (Partner − Propias) ÷ Propias × 100
```

Un valor negativo significa que el partner reporta menos que vos.

</details>

<br />

## ✦ Generar el .exe

Para compartir la app con alguien que no tiene Python, podés empaquetarla en un ejecutable de Windows (con `icono.ico` en la misma carpeta):

```bash
py -m pip install pyinstaller
py -m PyInstaller --onefile --windowed --icon=icono.ico adops_control_financiero.py
```

El resultado queda en la carpeta `dist/`. Hay que volver a generarlo cada vez que se modifique el código.

> La ventana ya incluye su propio icono dibujado por código. El archivo `icono.ico` solo se usa para el icono del `.exe`.

<br />

## ✦ Estructura del proyecto

```
.
├── adops_control_financiero.py   # La aplicación completa
├── icono.ico                     # Icono del ejecutable (opcional)
├── icono.png                     # Logo para este README
└── README.md
```

<br />

<div align="center">

<sub>Hecha con Python, tkinter y bastante mate · AdOps Control Financiero</sub>

</div>
