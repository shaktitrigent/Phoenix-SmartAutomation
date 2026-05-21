.PHONY: install package clean all

all: install package

install:
	pip install -e shared/ -q
	pip install -e phoenix-core/ -q
	pip install -e phoenix-intelligence/ -q
	pip install pyinstaller "uvicorn[standard]" -q

package:
	powershell -ExecutionPolicy Bypass -File build.ps1 package

clean:
	powershell -ExecutionPolicy Bypass -File build.ps1 clean
