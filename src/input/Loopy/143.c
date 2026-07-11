// Source: data/benchmarks/LinearArbitrary-SeaHorn/pie/hola/44.c

extern int unknown1();

void loopy_143(int k, int flag, int n)
{
  
  
  int i=0;
  int j=0;
  

  if (flag == 1){
     n=1;
  } else {
     n=2;
  }

  i=0;

  while ( i <= k){
    i++;
    j= j +n;
  }
  if(flag == 1)
      {;
//@ assert(j == i);
}

}
