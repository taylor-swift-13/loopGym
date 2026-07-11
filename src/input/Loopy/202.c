// Source: data/benchmarks/accelerating_invariant_generation/invgen/split.c

void loopy_202(int b, int j, int n) {
  int k = 100;
  
  int i;
  
  
  i = j;
  {
  n = 0;
  while (n < 2*k) {
    if(b) {
          i++;
        } else {
          j++;
        }
        b = !b;
    n++;
  }
}
  {;
//@ assert(i == j);
}

}