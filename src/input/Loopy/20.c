// Source: data/benchmarks/LinearArbitrary-SeaHorn/VeriMAP/TRACER-testloop29_VeriMAP_true.c

void errorFn() {ERROR: goto ERROR;}
void loopy_20(void) {
  int x = 0;
  while(x < 100) {
    x++;
    if(x == 50)
      break;
  }
  {;
//@ assert(!( x != 50 ));
}

}