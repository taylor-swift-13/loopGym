// Source: data/benchmarks/sv-benchmarks/loop-new/count_by_1_variant.c
#define LARGE_INT 1000000

void loopy_382(int i) {
    
    {
  i = 0;
  while (i != LARGE_INT) {
    {;
    //@ assert(i <= LARGE_INT);
    }
    i++;
  }
}
    return;
}