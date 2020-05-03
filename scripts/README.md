# How to use this code

1. Check out the repo https://github.com/<username>/cf-autotick-bot-test-package-feedstock.git

2. Add the upstream remote

   ```
   git remote add upstream https://github.com/conda-forge/cf-autotick-bot-test-package-feedstock.git
   ```

2. Run the script `run_tests.sh` feeding it the version number of the test as `vXYZ`
   (e.g., `./run_tests.sh v8`).

3. The script will make 9 PRs. Make sure those PRs pass and the bot has merged them.