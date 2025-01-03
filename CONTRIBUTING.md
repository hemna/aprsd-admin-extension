# CONTRIBUTING

Code contributions are welcomed and appreciated. Just submit a PR!

The current build environment uses `pre-commit`, and `uv`.

### Environment setup:

```console
pip install uv
git clone git@github.com:hemna/aprsd-admin-extension.git
cd aprsd-admin-extension
pre-commit install

# Optionally run the pre-commit scripts at any time
pre-commit run --all-files
```

### Running and testing:

From the aprstastic directory:

```console
cd aprsd-admin-extension
uv pip install https://github.com/craigerl/aprsd.git
uv pip install -e .

# Running
uv run aprsd admin web
```
