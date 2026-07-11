// Source: data/benchmarks/LinearArbitrary-SeaHorn/VeriMAP/TRACER-testloop15_VeriMAP_true.c

void errorFn() {ERROR: goto ERROR;}
void loopy_16(void)
{
  int i = 0;
  int N = 100;

  while (i<N) {
    i++;
  }

  {;
//@ assert(!( i>N ));
}

  return;
}