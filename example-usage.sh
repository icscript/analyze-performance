#!/bin/bash
# Example usage of compare-performance.py
# Demonstrates how to analyze validator performance after configuration changes

cd ~/cursor/projects/orc/turboflakes/
./compare-performance.py IC02KSM 51973 --network-normalized --last-change 51754 --peers -c "lat02 interrupt coelexcing rx usecs 50, could test going back 217 sessions"
./compare-performance.py IC03KSM 51976 --network-normalized --last-change 51754 --peers -c "lat03 interrupt coelexcing rx usecs 50"
./compare-performance.py IC01KSM 51976 --network-normalized --last-change 51754 --peers -c "lat01 4096 ring buffer"

./compare-performance.py $IC02KSM 51900 -b 144 --network-normalized

echo "================================================================"
echo "Example 1: Basic comparison (10 sessions before/after)"
echo "================================================================"
echo "Scenario: You changed CPU governor to performance at session 51400"
echo ""
./compare-performance.py $KUSAMA_VALIDATOR 51400 -b 10 -a 10
echo ""
echo "Press Enter to continue..."
read

echo "================================================================"
echo "Example 2: Detailed analysis with component breakdown"
echo "================================================================"
echo "Scenario: You optimized network buffer settings at session 51420"
echo ""
./compare-performance.py $KUSAMA_VALIDATOR 51420 -b 5 -a 5 -d
echo ""
echo "Press Enter to continue..."
read

echo "================================================================"
echo "Example 3: JSON output for automation"
echo "================================================================"
echo "Scenario: Automated performance tracking for multiple changes"
echo ""
./compare-performance.py $KUSAMA_VALIDATOR 51400 -b 10 -a 10 --json | jq '.improvement'
echo ""
echo "Press Enter to continue..."
read

echo "================================================================"
echo "Example 4: Polkadot validator analysis"
echo "================================================================"
echo ""
./compare-performance.py $POLKADOT_VALIDATOR 12345 -n polkadot -b 10 -a 10
./compare-performance.py 15zH8tbFxyBgvkAdF3UWSfykAXADbS32vJuYRHTkZJ15Y4jd 11788 -n polkadot -b 24
./compare-performance.py 12Qq3fn9xnFZ37Ltcj6BH8NSpAQjEMp2oKnEALa7bbuguU4L 11776 -n polkadot
echo ""

echo "================================================================"
echo "Example 5: Finding optimal sample size"
echo "================================================================"
echo "Compare with different session ranges to find stable results:"
echo ""
echo "5 sessions:"
./compare-performance.py $KUSAMA_VALIDATOR 51400 -b 5 -a 5 | grep "Score Change"
echo ""
echo "10 sessions:"
./compare-performance.py $KUSAMA_VALIDATOR 51400 -b 10 -a 10 | grep "Score Change"
echo ""
echo "20 sessions:"
./compare-performance.py $KUSAMA_VALIDATOR 51400 -b 20 -a 20 | grep "Score Change"
echo ""
echo "If results are consistent across ranges, the change impact is clear."
echo ""
