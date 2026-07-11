// Source: data/benchmarks/sv-benchmarks/loop-crafted/simple_vardep_1.c

void loopy_351(void)
{
  unsigned int i = 0;
  unsigned int j = 0;
  unsigned int k = 0;

  while (k < 0x0fffffff) {
    i = i + 1;
    j = j + 2;
    k = k + 3;

    {;
//@ assert(k == (i + j));
}

  }

}