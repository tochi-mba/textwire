.DEFAULT_GOAL := help

.PHONY: help doctor install check server-check vectors vectors-check android-check android-apk \
	android-install simulate run clean site site-serve bench bench-record

help: ## Show available targets
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-16s\033[0m %s\n", $$1, $$2}'

doctor: ## Check this machine for everything the repository needs
	@sh tools/doctor.sh

install: ## Install the server's virtualenv
	$(MAKE) -C server install

check: server-check vectors-check android-check ## Every gate CI runs

server-check: ## Server: lint, types, import contracts, tests at 100% branch coverage
	$(MAKE) -C server check

vectors: ## Regenerate the golden vectors from the Python reference
	$(MAKE) -C server vectors

vectors-check: ## Fail if the committed golden vectors drifted
	$(MAKE) -C server vectors-check

# Without a JDK the Android half is skipped locally, and never in CI.
android-check: ## Android: ktlint, unit tests, coverage floors
	@if command -v java >/dev/null 2>&1; then \
		cd android && ./gradlew check --console=plain; \
	elif [ -n "$$CI" ]; then \
		echo "android: a JDK 17 is required in CI" >&2; exit 1; \
	else \
		echo "android: skipped, no JDK 17 on PATH (see docs/ONBOARDING.md)"; \
	fi

android-apk: ## Build the debug APK into dist/
	cd android && ./gradlew :app:assembleDebug --console=plain
	mkdir -p dist
	cp android/app/build/outputs/apk/debug/app-debug.apk dist/textwire-debug.apk
	@echo "dist/textwire-debug.apk"

android-install: android-apk ## Install the debug APK on the phone adb sees (ANDROID_SERIAL picks one)
	adb install -r dist/textwire-debug.apk

simulate: ## Browse from the terminal with a virtual phone and recorded pages
	$(MAKE) -C server simulate

run: ## Run the server
	$(MAKE) -C server run

bench: ## SMS per page and pipeline speed, server and phone, against benchmarks/
	$(MAKE) -C server bench
	@if command -v java >/dev/null 2>&1; then cd android && ./gradlew :core:bench --console=plain -q; \
	else echo "phone bench: skipped, no JDK 17 on PATH"; fi

bench-record: ## Record this checkout's numbers as the new baselines in benchmarks/
	$(MAKE) -C server bench-record
	@if command -v java >/dev/null 2>&1; then cd android && ./gradlew :core:bench -Precord --console=plain -q; \
	else echo "phone bench: skipped, no JDK 17 on PATH"; fi

site: ## Build the Pages site (landing page and handbook) into build/site; a broken link fails
	cd server && uv run python scripts/build_site.py

site-serve: ## Serve the handbook with live reload
	cd server && uv run python scripts/build_site.py --serve

clean: ## Remove build output
	$(MAKE) -C server clean
	rm -rf dist build
	@if [ -x android/gradlew ] && command -v java >/dev/null 2>&1; then cd android && ./gradlew clean -q; fi
