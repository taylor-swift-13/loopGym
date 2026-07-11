// Source: data/benchmarks/LinearArbitrary-SeaHorn/pie/hola/42.c

extern int unknown1();
extern int unknown2();

void loopy_141(int flag)
{
  
  int x = 1;
  int y = 1;
  int a;
  
  if(flag)
    a = 0;
  else
    a = 1;

  while(unknown1()){
    if(flag)
    {
      a = x+y;
      x++;
    }
    else
    {
      a = x+y+1;
      y++;
    }
    if(a%2==1)
      y++;
    else
      x++;	  
  }
  
  if(flag)
    a++;
  {;
//@ assert(a%2==1);
}

}