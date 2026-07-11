// Adapted from Loopy: sv-benchmarks/loop-floats-scientific-comp/loop2-2.c
// Fixed-point scale: 1000; pi is rounded to 3142.
int unknown_int(void);

/*@ requires 1047 < x && x < 3142; */
void loopy_354(int x) {
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

  /*@ assert odd_exp >= even_exp; */
}
