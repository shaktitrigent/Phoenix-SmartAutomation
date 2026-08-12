        if slow:
            env["PWSLOWMO"] = str(slow)

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=Path.cwd(), env=env)