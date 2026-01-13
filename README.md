# Typify Project

Typify is a **usage-driven static type inference engine for Python** that automatically predicts precise type annotations for variables, parameters, and return values, even in largely or fully unannotated codebases.  
This repository serves as the **official replication package** for Typify, providing datasets, command-line tooling, and evaluation scripts required to reproduce experimental results.

Typify performs **multi-pass, interprocedural static analysis** driven by observed call-site behavior. Inference is resolved through **recursive fixpoint iteration** and **accumulative type unification**, enabling robust handling of real-world Python features such as generics, unions, and recursion.

---

## Key Capabilities

- **Usage-driven inference** based on concrete call-site interactions  
- **Recursive and interprocedural analysis** with fixpoint convergence  
- Native support for:
  - Dependency graph generation based on project structure
  - Inference based on function call
  - Type propagation across method calls
  - Custom generic and parametric types
- **Incremental analysis and global caching** for scalability on large projects  
- End-to-end **benchmarking and evaluation framework**

---

## Installation

We recommend installing Typify in a fresh Python environment to avoid dependency conflicts.

```bash
# Create a new environment
conda create -n typify-env python=3.9 -y
conda activate typify-env

# Clone the repository
git clone https://github.com/typify-contributor/typify.git
cd typify

# Install in editable mode
pip install -e typify
```

---

## Datasets

All datasets used in the evaluation are uploaded to Google Drive and can be accessed [here](https://drive.google.com/file/d/1qyeZ3SrGXuAF2qwXnv3omGaMVi9WRpWu/view?usp=sharing).  
The `typify-datasets.zip` file contains:


- **ManyTypes4Py** (`mt4py.zip`)  
- **Typilus** (`typilus.zip`)  
- **Sample dataset** (`sample.zip`)  

Each dataset consists of Python projects with ground-truth annotations suitable for benchmarking static type inference tools.

---

## Evaluation Pipeline

Typify evaluation consists of three stages:

1. **Ground-truth extraction**
2. **Type inference**
3. **Result evaluation**

### 1. Ground-Truth Extraction (`typify gt`)

Extracts annotated types from a dataset and produces a JSON ground-truth file.

```bash
Usage: typify gt [DATASET_DIR] [--paths-txt PATHS_TXT] [--output-types OUTPUT_TYPES]

Arguments:
  DATASET_DIR PATH       Path to the dataset directory

Options:
  --output-types PATH    Output JSON file containing extracted annotations
  --paths-txt PATH       Optional file listing relative paths to analyze
```

---

### 2. Running Typify (`typify dataset`)

Runs Typify over a dataset and produces inferred type predictions.

```bash
Usage: typify dataset [DATASET_DIR] [OPTIONS]

Arguments:
  DATASET_DIR PATH       Path to the dataset directory

Options:
  --output-types PATH    Output JSON file for inferred types
  --topn INTEGER         Number of top-ranked predictions to retain
```

---

### 3. Evaluation (`typify eval`)

Compares inferred types against ground truth using exact and base-type matching.

```bash
Usage: typify eval [GT_PATH] [TOOL_PATH] [--topn N]

Arguments:
  GT_PATH PATH    Ground-truth JSON file
  TOOL_PATH PATH  Inference output JSON file

Options:
  --topn INTEGER  Evaluate using Top-N predictions (default: 1)
```

---

## Example: Sample Dataset

The `sample.zip` dataset contains 64 Python repositories and can be used for a quick end-to-end evaluation.

```bash
# Step 1: Extract ground truth
typify gt '/sample' --output-types '/gt.json'

# Step 2: Run Typify
typify dataset '/sample' --output-types '/tool.json' --topn 5

# Step 3: Evaluate results
typify eval '/gt.json' '/tool.json' --topn 5
```

---

## Example: ManyTypes4Py Dataset

To evaluate Typify on the ManyTypes4Py dataset:

```bash
# Step 1: Ground truth extraction
typify gt '/mt4py' --paths-txt 'mt4py-files.txt' --output-types '/gt.json'

# Step 2: Run Typify
typify dataset '/mt4py' --output-types '/tool.json' --topn 5

# Step 3: Evaluation
typify eval '/gt.json' '/tool.json' --topn 5
```

---

## Running Typify on a Single Project

Typify can also be applied to individual Python projects.

```bash
Usage: typify project [PROJECT_PATH] [--output-types OUTPUT_TYPES] [--topn N]

Arguments:
  PROJECT_PATH PATH      Path to a Python project

Options:
  --output-types PATH    Output JSON file for inferred types
  --topn INTEGER         Number of top-ranked predictions
```

A small example project (`sample_project`) is included in this repository:

```bash
typify project sample_project
```

Inferred types will be written to `sample_project/.typify/`.

---

## Development Notes

- Requires **Python 3.9 or later**
- Supported on **Linux, macOS, and Windows**
- Designed for both **single-project analysis** and **large-scale dataset benchmarking**

---

## License

Typify is released under the **MIT License**.  
See the `LICENSE` file for details.
