// Adapted from Loopy: sv-benchmarks/loop-floats-scientific-comp/loop1-1.c
// Fixed-point scale: 1000.
int unknown_int(void);

/*@ requires -1000 < x && x < 1000; */
void loopy_353(int x) {
  int exp = 1000;
  int term = 1000;
  int count = 1;
  int result = 2000000 / (1000 - x);
  int keep_going = 1;

  while (keep_going != 0) {
    term = (term * x) / (count * 1000);
    exp = exp + term;
    count = count + 1;
    keep_going = unknown_int();
  }

  /*@ assert result >= exp; */
}
