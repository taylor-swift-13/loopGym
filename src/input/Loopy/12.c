// Source: data/benchmarks/LinearArbitrary-SeaHorn/VeriMAP/TRACER-testloop10_VeriMAP_true.c
extern int unknown(void);
extern unsigned int unknown_uint(void);

int unknown(){int x; return x;}

void errorFn() {ERROR: goto ERROR;}

void loopy_12(int old)
{
  int lock, new;
  lock=0;
  new=old+1;

  while (new != old) {
    lock = 1;
    old = new;
    if (unknown()) {
      lock = 0;
      new++;
    }
  }

  {;
//@ assert(!( lock==0 ));
}

return;

}