// Source: data/benchmarks/LinearArbitrary-SeaHorn/pie/ICE/benchmarks/sum04.c

#define a (1)
#define SIZE 8
void loopy_107(int i) { 
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
