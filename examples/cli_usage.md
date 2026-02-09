# Phoenix CLI Usage Examples

## Initialize Project

```bash
# Initialize a new Phoenix project
phoenix init --project-name my-project
```

## Generate Tests

### Basic Generation

```bash
# Generate both manual and automation tests
phoenix generate \
  --story "As a user, I want to login" \
  --criteria "User can enter credentials" \
  --criteria "User can click login button" \
  --criteria "User is redirected after login"
```

### Generate Only Manual Tests

```bash
phoenix generate \
  --story "As a user, I want to login" \
  --criteria "User can enter credentials" \
  --type manual \
  --risk smoke
```

### Generate Only Automation Tests

```bash
phoenix generate \
  --story "As a user, I want to login" \
  --criteria "User can enter credentials" \
  --type automation \
  --project my-project
```

## Execute Tests

### Execute All Tests in Project

```bash
phoenix execute --project my-project
```

### Execute Specific Tests

```bash
phoenix execute \
  --project my-project \
  --test-ids 1 \
  --test-ids 2 \
  --test-ids 3
```

### Execute with Specific Browser

```bash
phoenix execute \
  --project my-project \
  --browser chromium
```

## Verbose Mode

Add `--verbose` or `-v` to any command for detailed output:

```bash
phoenix generate --story "..." --criteria "..." --verbose
```

## Configuration

Use `--config` or `-c` to specify a configuration file:

```bash
phoenix generate --config config.yaml --story "..."
```
