// Source: data/benchmarks/accelerating_invariant_generation/crafted/simple_safe3.c

/*@
  requires N <= 65535;
*/
void loopy_169(unsigned int N) {
  unsigned int x = 0;
  

  while (x < N) {
    x += 2;
  }

  {;
//@ assert(!(x % 2));
}

}