name: Scrape y publicar promociones (Panamá)

on:
  schedule:
    # 6:00 AM y 6:00 PM (hora de Panamá) = 11:00 y 23:00 UTC
    - cron: '0 11,23 * * *'
  workflow_dispatch:

permissions:
  contents: write
  pages: write
  id-token: write

jobs:
  scrape-and-deploy:
    runs-on: ubuntu-latest

    steps:
      # ==============================================
      # 1. PREVENCIÓN DE ERROR DE GIT LFS
      # ==============================================
      - name: Instalar Git LFS
        run: |
          sudo apt-get update
          sudo apt-get install -y git-lfs
          git lfs install

      # ==============================================
      # 2. CHECKOUT DEL REPOSITORIO
      # ==============================================
      - name: Checkout repositorio
        uses: actions/checkout@v4
        with:
          lfs: true
          persist-credentials: true

      # ==============================================
      # 3. CONFIGURAR PYTHON
      # ==============================================
      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.10'

      # ==============================================
      # 4. INSTALAR SOLO GOOGLE CHROME (SIN CHROMEDRIVER)
      # ==============================================
      - name: Instalar Google Chrome
        run: |
          sudo apt-get update
          sudo apt-get install -y wget
          wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | sudo apt-key add -
          sudo sh -c 'echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list'
          sudo apt-get update
          sudo apt-get install -y google-chrome-stable
          google-chrome --version

      # ==============================================
      # 5. INSTALAR DEPENDENCIAS DE PYTHON
      # ==============================================
      - name: Instalar dependencias Python
        run: |
          if [ -f requirements.txt ]; then
            pip install -r requirements.txt
          else
            pip install requests pandas openpyxl beautifulsoup4 lxml selenium webdriver-manager
          fi

      # ==============================================
      # 6. EJECUTAR SCRAPER
      # ==============================================
      - name: Ejecutar Scraper
        run: python scraper_super.py

      # ==============================================
      # 7. EJECUTAR MOTOR IA
      # ==============================================
      - name: Ejecutar Motor AI Engine
        run: python ai_engine.py

      # ==============================================
      # 8. LISTAR ARCHIVOS GENERADOS (DEPURACIÓN)
      # ==============================================
      - name: Listar archivos generados
        run: |
          echo "=== Archivos en data/ ==="
          ls -la data/ || echo "data/ no existe"
          echo "=== Archivos en web/ ==="
          ls -la web/ || echo "web/ no existe"

      # ==============================================
      # 9. COMMIT Y PUSH DE ARCHIVOS GENERADOS
      # ==============================================
      - name: Commit y Push de archivos generados
        run: |
          git config --global user.name 'github-actions[bot]'
          git config --global user.email 'github-actions[bot]@users.noreply.github.com'
          git add data/ web/data.json
          if [ -n "$(git status --porcelain)" ]; then
            git commit -m "Actualización automática de precios y data.json"
            git push
          else
            echo "No hay cambios nuevos para commitar."
          fi

      # ==============================================
      # 10. CONFIGURAR Y DESPLEGAR EN GITHUB PAGES
      # ==============================================
      - name: Configurar Pages
        uses: actions/configure-pages@v5

      - name: Subir artefacto (carpeta web)
        uses: actions/upload-pages-artifact@v3
        with:
          path: './web'

      - name: Desplegar a GitHub Pages
        id: deployment
        uses: actions/deploy-pages@v4
