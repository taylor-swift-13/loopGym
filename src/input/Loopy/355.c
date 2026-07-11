// Adapted from Loopy: sv-benchmarks/loop-floats-scientific-comp/loop3.c
// Fixed-point scale: 1000; pi/8 is rounded to 393.
int unknown_int(void);

/*@ requires 0 < x && x < 393; */
void loopy_355(int x) {
  int odd_exp = x;
  int even_exp = 1000;
  int term = x;
  int count = 2;
  int multiplier = 0;
  int keep_going = 1;

  while (keep_going != 0) {
    term = (term * x) / (count * 1000);
    multiplier = ((count >> (1 % 2)) == 0) ? 1 : -1;
    even_exp = even_exp + multiplier * term;
    count = count + 1;
    term = (term * x) / (count * 1000);
    odd_exp = odd_exp + multiplier * term;
    count = count + 1;
    keep_going = unknown_int();
  }

  /*@ assert even_exp >= odd_exp; */
}
