// Source: data/benchmarks/LinearArbitrary-SeaHorn/VeriMAP/TRACER-testloop14_VeriMAP_true.c
extern unsigned int unknown_uint(void);

void errorFn() {ERROR: goto ERROR;}
void loopy_15(int i, int x, int y)
{
  if (y <= 2) {
    if (x < 0) {
      x = 0;
    }
    i = 0;
    while (i < 10) {
      {;
//@ assert(!( y > 2 ));
}

      i++;
    }

    {;
//@ assert(!( x <= -1 ));
}

  }
  return;
}