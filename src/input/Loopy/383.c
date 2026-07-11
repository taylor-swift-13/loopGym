// Source: data/benchmarks/sv-benchmarks/loop-new/count_by_2.c
#define LARGE_INT 1000000

void loopy_383(int i) {
    
    {
  i = 0;
  while (i < LARGE_INT) {
    i += 2;
  }
}
    {;
//@ assert(i == LARGE_INT);
}

    return;
}