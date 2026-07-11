// Source: data/benchmarks/LinearArbitrary-SeaHorn/pie/ICE/benchmarks/sum04_safe.c

#define a (1)
#define SIZE 8
void loopy_108(int i) { 
  int sn=0;
  {
  i=1;
  while (i<=SIZE) {
    sn = sn + a;
    i++;
  }
}
  {;
//@ assert(sn==SIZE*a || sn == 0);
}

}
